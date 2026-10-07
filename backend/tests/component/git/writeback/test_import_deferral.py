from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.protocols import CoreGraphQLQuery, CoreRepository

from infrahub import config, lock
from infrahub.core.constants import RepositoryOperationalStatus
from infrahub.core.initialization import create_branch
from infrahub.core.registry import registry
from infrahub.git import InfrahubRepository
from infrahub.git.tasks import bootstrap_local_repository
from infrahub.git.writeback.store import build_intent_store
from infrahub.services import InfrahubServices
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.flow import call_in_flow
from tests.helpers.git import LocalRemote
from tests.helpers.graphql import graphql_mutation
from tests.helpers.repository_sync import FLOW_RUN_LOGGER, create_repository_node, run_add_flow, run_sync_flow
from tests.helpers.test_app import TestInfrahubApp

from .conftest import create_repository, pending_merge

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

TRUNK = "main"
SYNC_LOGGER = "infrahub.tasks"
EMPTY_CONFIG = "---\n"
REIMPORT = """
mutation InfrahubRepositoryProcess($id: String!) {
    InfrahubRepositoryProcess(data: {id: $id}) {
        ok
    }
}
"""


@dataclass(frozen=True)
class DeliveryStateCase:
    name: str
    pending: bool


DELIVERY_STATE_CASES: list[DeliveryStateCase] = [
    DeliveryStateCase(name="pending", pending=True),
    DeliveryStateCase(name="nothing-pending", pending=False),
]


def query_files(query_name: str) -> dict[str, str]:
    return {
        ".infrahub.yml": f"queries:\n  - name: {query_name}\n    file_path: query.gql\n",
        "query.gql": f"query {query_name} {{\n  CoreRepository {{\n    edges {{\n      node {{\n        id\n      }}\n    }}\n  }}\n}}\n",
    }


async def enqueue_merge(db: InfrahubDatabase, repository_id: str, source_git_branch: str) -> None:
    store = await build_intent_store(db=db, lock_registry=lock.registry)
    await store.enqueue(
        repository_id=repository_id,
        entry=pending_merge(entry_id="merge-1", source_git_branch=source_git_branch),
        widen=False,
    )


@pytest.mark.parametrize("branch_name", [TRUNK, "feature-reimport"])
async def test_reimport_is_refused_on_every_branch_while_a_push_is_pending(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, branch_name: str
) -> None:
    repository = await create_repository(db=db, branch=default_branch, name="pending-repository")
    await enqueue_merge(db=db, repository_id=repository.id, source_git_branch="feature-1")
    branch = default_branch if branch_name == TRUNK else await create_branch(branch_name=branch_name, db=db)
    workflow = WorkflowRecorder()
    service = await InfrahubServices.new(database=db, workflow=workflow)

    result = await graphql_mutation(
        query=REIMPORT, db=db, branch=branch, variables={"id": repository.id}, service=service
    )

    assert result.errors
    assert [error.message for error in result.errors] == [
        "Repository pending-repository has pending pushes; a reimport now would remove the objects they added. "
        "Retry or abandon the pending pushes first."
    ]
    assert workflow.submit_calls == []


class TestImportDeferral(TestInfrahubApp):
    """A synchronisation and a seed import against a local remote, while merged changes wait for their push."""

    @pytest.fixture(autouse=True)
    def every_remote_branch_is_imported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config.SETTINGS.git, "import_sync_branch_names", [])

    async def _add(self, db: InfrahubDatabase, remote: LocalRemote, name: str) -> Node:
        node = await create_repository_node(
            db=db,
            name=name,
            location=str(remote.directory),
            default_branch=TRUNK,
            operational_status=RepositoryOperationalStatus.ONLINE.value,
        )
        state = await run_add_flow(node=node, name=name, location=str(remote.directory))
        assert state.is_completed()
        return node

    async def _worker_commit(
        self, client: InfrahubClient, node: Node, name: str, remote: LocalRemote, branch_name: str
    ) -> str:
        repo = await InfrahubRepository.init(
            id=node.id,
            name=name,
            location=str(remote.directory),
            client=client,
            infrahub_branch_name=registry.default_branch,
        )
        return repo.get_commit_value(branch_name=branch_name, remote=False)

    async def _graph_commit(self, client: InfrahubClient, node: Node, branch_name: str) -> str:
        repository = await client.get(kind=CoreRepository, id=node.id, branch=branch_name)
        return repository.commit.value

    async def _query_names(self, client: InfrahubClient, node: Node) -> set[str]:
        queries = await client.filters(kind=CoreGraphQLQuery, repository__ids=[node.id])
        return {query.name.value for query in queries}

    @pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in DELIVERY_STATE_CASES])
    async def test_sync_leaves_the_default_branch_while_a_push_is_pending(
        self,
        case: DeliveryStateCase,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        caplog.set_level(logging.INFO, logger=SYNC_LOGGER)
        name = f"trunk-{case.name}"
        query_name = f"trunk_{case.name.replace('-', '_')}"
        other_branch = f"other-{case.name}"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[])
        imported = remote.commit(branch_name=TRUNK, files=query_files(query_name))
        node = await self._add(db=db, remote=remote, name=name)
        await create_branch(branch_name=other_branch, db=db)
        other_commit = remote.commit(branch_name=other_branch, files={"data.txt": "other\n"})
        advanced = remote.commit(branch_name=TRUNK, files={".infrahub.yml": EMPTY_CONFIG})
        if case.pending:
            await enqueue_merge(db=db, repository_id=node.id, source_git_branch="merged-feature")

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_completed()
        trunk_commit = imported if case.pending else advanced
        assert (
            await self._worker_commit(client=client, node=node, name=name, remote=remote, branch_name=TRUNK)
            == trunk_commit
        )
        assert await self._graph_commit(client=client, node=node, branch_name=TRUNK) == trunk_commit
        assert await self._query_names(client=client, node=node) == ({query_name} if case.pending else set())
        assert await self._graph_commit(client=client, node=node, branch_name=other_branch) == other_commit
        assert [
            record.getMessage()
            for record in caplog.records
            if record.name == SYNC_LOGGER and record.getMessage().startswith("Skipped the synchronization")
        ] == (
            [
                f"Skipped the synchronization of branches {TRUNK} of repository {name}: "
                "a push of merged changes to the remote is pending"
            ]
            if case.pending
            else []
        )

    @pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in DELIVERY_STATE_CASES])
    async def test_sync_creates_no_branch_for_the_source_of_a_pending_push(
        self,
        case: DeliveryStateCase,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = f"new-source-{case.name}"
        source_branch = f"new-source-{case.name}"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[])
        node = await self._add(db=db, remote=remote, name=name)
        remote.commit(branch_name=source_branch, files={"data.txt": "source\n"})
        if case.pending:
            await enqueue_merge(db=db, repository_id=node.id, source_git_branch=source_branch)

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_completed()
        assert {source_branch} & set(await client.branch.all()) == (set() if case.pending else {source_branch})

    @pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in DELIVERY_STATE_CASES])
    async def test_sync_does_not_advance_the_source_branch_of_a_pending_push(
        self,
        case: DeliveryStateCase,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        tmp_path: Path,
        git_repos_dir: Path,
    ) -> None:
        name = f"kept-source-{case.name}"
        source_branch = f"kept-source-{case.name}"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[source_branch])
        kept = remote.repo.commit(source_branch).hexsha
        node = await self._add(db=db, remote=remote, name=name)
        assert await self._graph_commit(client=client, node=node, branch_name=source_branch) == kept
        advanced = remote.commit(branch_name=source_branch, files={"data.txt": "advanced\n"})
        if case.pending:
            await enqueue_merge(db=db, repository_id=node.id, source_git_branch=source_branch)

        state = await run_sync_flow(client=client, repository_id=node.id, name=name, location=str(remote.directory))

        assert state.is_completed()
        source_commit = kept if case.pending else advanced
        assert (
            await self._worker_commit(client=client, node=node, name=name, remote=remote, branch_name=source_branch)
            == source_commit
        )
        assert await self._graph_commit(client=client, node=node, branch_name=source_branch) == source_commit

    @pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in DELIVERY_STATE_CASES])
    async def test_seed_import_after_a_fresh_clone_leaves_the_default_branch_while_a_push_is_pending(
        self,
        case: DeliveryStateCase,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initialize_registry: None,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
        git_repos_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        caplog.set_level(logging.INFO, logger=FLOW_RUN_LOGGER)
        name = f"seed-{case.name}"
        query_name = f"seed_{case.name.replace('-', '_')}"
        remote = LocalRemote.create(directory=tmp_path / name, trunk=TRUNK, branches=[])
        remote.commit(branch_name=TRUNK, files=query_files(query_name))
        node = await self._add(db=db, remote=remote, name=name)
        advanced = remote.commit(branch_name=TRUNK, files={".infrahub.yml": EMPTY_CONFIG})
        if case.pending:
            await enqueue_merge(db=db, repository_id=node.id, source_git_branch="merged-feature")
        fresh_worker_dir = tmp_path / "fresh-worker-repositories"
        fresh_worker_dir.mkdir()
        monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(fresh_worker_dir))
        repository = await client.get(kind=CoreRepository, id=node.id)
        state = await build_intent_store(db=db, lock_registry=lock.registry)

        repo = await call_in_flow(
            lambda: bootstrap_local_repository(
                repo_name=name,
                repository=repository,
                infrahub_branch=registry.default_branch,
                client=client,
                state=state,
            )
        )

        assert repo is not None
        assert repo.get_commit_value(branch_name=TRUNK, remote=False) == advanced
        assert await self._query_names(client=client, node=node) == ({query_name} if case.pending else set())
        assert [
            record.getMessage()
            for record in caplog.records
            if record.name == FLOW_RUN_LOGGER and record.getMessage().startswith("Skipped the import")
        ] == (
            [
                f"Skipped the import of the default branch {TRUNK} of repository {name}: "
                "a push of merged changes to the remote is pending"
            ]
            if case.pending
            else []
        )
