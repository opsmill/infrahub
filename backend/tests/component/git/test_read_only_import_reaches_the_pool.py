"""Importing the latest commit of a read-only repository reaches every worker, not only the importing one."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.node import Node
from infrahub.git.models import GitRepositoryPullReadOnly
from infrahub.git.repository import InfrahubReadOnlyRepository
from infrahub.message_bus.messages import RefreshGitFetch
from infrahub.workflows.catalogue import GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT, GIT_REPOSITORIES_PULL_READ_ONLY
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.git import LocalRemote
from tests.helpers.test_app import TestInfrahubApp
from tests.helpers.test_client import dummy_async_request

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.message_bus import InfrahubMessage
    from infrahub.services import InfrahubServices
    from tests.adapters.cache import MemoryCache
    from tests.adapters.message_bus import BusSimulator

IMPORT_LAST_COMMIT = """
mutation InfrahubReadOnlyRepositoryImportLastCommit($id: String!) {
    InfrahubReadOnlyRepositoryImportLastCommit(data: {id: $id}) {
        ok
    }
}
"""


class TestImportLatestCommitReachesThePool(TestInfrahubApp):
    @pytest.fixture
    def api_workflow(self, service: InfrahubServices) -> Generator[WorkflowRecorder, None, None]:
        """Record what the API submits instead of running it, so each submission runs as its own worker would."""
        original = service._workflow
        recorder = WorkflowRecorder()
        service._workflow = recorder
        try:
            yield recorder
        finally:
            service._workflow = original

    async def test_a_new_commit_is_broadcast_through_the_pull_its_commit_update_submits(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        initialize_registry: None,
        bus_simulator: BusSimulator,
        memory_cache: MemoryCache,
        git_repos_dir: Path,
        tmp_path: Path,
        api_workflow: WorkflowRecorder,
    ) -> None:
        name = "import-latest-repo"
        remote = LocalRemote.create(directory=tmp_path / name, trunk="main", branches=[])
        imported_commit = remote.repo.head.commit.hexsha
        node = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY)
        await node.new(
            db=db,
            name=name,
            location=str(remote.directory),
            ref="main",
            commit=imported_commit,
            internal_status=RepositoryInternalStatus.ACTIVE.value,
        )
        await node.save(db=db)
        # This worker's copy, cloned without writing the commit back so the setup submits nothing.
        await InfrahubReadOnlyRepository.new(
            id=UUID(node.id),
            name=name,
            location=str(remote.directory),
            ref="main",
            infrahub_branch_name=default_branch.name,
            client=InfrahubClient(config=Config(requester=dummy_async_request)),
        )
        latest_commit = remote.commit(branch_name="main", files={"data.txt": "v2\n"})

        await client.execute_graphql(query=IMPORT_LAST_COMMIT, variables={"id": node.id})
        assert [call["workflow"] for call in api_workflow.submit_calls] == [GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT]

        broadcasts_before_import = len(bus_simulator.messages)
        await _run(api_workflow.submit_calls[0])

        # The pull the import's commit update submits is what tells the pool, so the import itself sends nothing.
        assert _fetches_for(bus_simulator.messages[broadcasts_before_import:], repository_id=node.id) == []
        pulls = api_workflow.get_submit_calls_for(workflow=GIT_REPOSITORIES_PULL_READ_ONLY)
        assert [pull["parameters"] for pull in pulls] == [
            {
                "model": GitRepositoryPullReadOnly(
                    location=str(remote.directory),
                    repository_id=node.id,
                    repository_name=name,
                    ref="main",
                    commit=latest_commit,
                    infrahub_branch_name=default_branch.name,
                    infrahub_branch_id=str(default_branch.get_uuid()),
                )
            }
        ]

        broadcasts_before_pull = len(bus_simulator.messages)
        await _run(pulls[0])

        assert _fetches_for(bus_simulator.messages[broadcasts_before_pull:], repository_id=node.id) == [
            (default_branch.name, str(default_branch.get_uuid()), latest_commit, InfrahubKind.READONLYREPOSITORY)
        ]
        # The pull writes a commit the graph already holds, so it does not submit another pull.
        assert len(api_workflow.get_submit_calls_for(workflow=GIT_REPOSITORIES_PULL_READ_ONLY)) == 1


async def _run(submission: dict[str, Any]) -> None:
    await submission["workflow"].load_function()(**submission["parameters"])


def _fetches_for(sent: list[InfrahubMessage], repository_id: str) -> list[tuple[str, str, str | None, str]]:
    return [
        (message.infrahub_branch_name, message.infrahub_branch_id, message.commit, message.repository_kind)
        for message in sent
        if isinstance(message, RefreshGitFetch) and message.repository_id == repository_id
    ]
