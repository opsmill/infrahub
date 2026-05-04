from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.git.models import GitRepositoryNodeQuery
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestGitBranchTaskOptimization(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def repos_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        default_branch: Branch,
        bus_simulator: BusSimulator,
    ) -> list[str]:
        repo_ids = []
        for _idx, name in enumerate(["opt-repo-alpha", "opt-repo-beta", "opt-repo-gamma"]):
            repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
            await repo.new(
                db=db,
                name=name,
                location=f"git@github.com:test/{name}.git",
            )
            await repo.save(db=db)
            repo_ids.append(repo.id)
        return repo_ids

    async def test_git_repository_node_query_returns_all_repos(
        self,
        db: InfrahubDatabase,
        repos_dataset: list[str],
        default_branch: Branch,
        client: InfrahubClient,
        prefect_test_fixture: None,
    ) -> None:
        repo_query = GitRepositoryNodeQuery()
        response = await client.execute_graphql(query=repo_query.render_query())
        nodes = repo_query.parse_response(response=response)

        returned_ids = {node.id for node in nodes}
        assert set(repos_dataset).issubset(returned_ids)
