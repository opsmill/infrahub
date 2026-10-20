from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from git import Repo

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreRepository
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

COMMIT_LOG_ROUTING_KEY = "git.commit_log.get"

COMMITS_QUERY = """
query RepositoryCommits($id: String!) {
  InfrahubRepositoryCommits(repository_id: $id, limit: 100) {
    branch_name
    git_ref
    condition
    imported_commit
    remote_head
    pending_count
    unavailable { reason }
    edges { node { hash state } }
  }
}
"""

INFRAHUB_SIDE_ONLY_QUERY = """
query RepositoryCommits($id: String!) {
  InfrahubRepositoryCommits(repository_id: $id) {
    branch_name
    git_ref
    imported_commit
  }
}
"""


class TestRepositoryCommitsQuery(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        git_repos_source_dir_module_scope: Path,
    ) -> None:
        await load_schema(db, schema=CAR_SCHEMA)
        FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)
        # The repository declares a check targeting this group, so the import fails without it.
        people = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await people.new(db=db, name="people")
        await people.save(db=db)

    @pytest.fixture(scope="class")
    async def repository(
        self,
        db: InfrahubDatabase,
        initial_dataset: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
    ) -> CoreRepository:
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
        )
        await client_repository.save()

        return await NodeManager.get_one(db=db, id=client_repository.id, kind=CoreRepository, raise_on_error=True)

    async def test_commit_log_is_read_from_the_worker_clone(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        repository: CoreRepository,
        git_repos_source_dir_module_scope: Path,
        bus_simulator: BusSimulator,
    ) -> None:
        upstream = Repo(git_repos_source_dir_module_scope / "car-dealership")
        history = upstream.git.rev_list("main").splitlines()
        requests_before = len(bus_simulator.messages_per_routing_key.get(COMMIT_LOG_ROUTING_KEY, []))

        response = await client.execute_graphql(query=COMMITS_QUERY, variables={"id": repository.id})

        assert repository.commit.value == history[0]
        assert response["InfrahubRepositoryCommits"] == {
            "branch_name": default_branch.name,
            "git_ref": "main",
            "condition": "IN_SYNC",
            "imported_commit": history[0],
            "remote_head": history[0],
            "pending_count": None,
            "unavailable": None,
            "edges": [{"node": {"hash": history[0], "state": "IMPORTED"}}]
            + [{"node": {"hash": commit_hash, "state": "HISTORY"}} for commit_hash in history[1:]],
        }
        assert len(bus_simulator.messages_per_routing_key[COMMIT_LOG_ROUTING_KEY]) == requests_before + 1

    async def test_infrahub_side_fields_make_no_worker_request(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        repository: CoreRepository,
        bus_simulator: BusSimulator,
    ) -> None:
        requests_before = len(bus_simulator.messages_per_routing_key.get(COMMIT_LOG_ROUTING_KEY, []))

        response = await client.execute_graphql(query=INFRAHUB_SIDE_ONLY_QUERY, variables={"id": repository.id})

        assert response["InfrahubRepositoryCommits"] == {
            "branch_name": default_branch.name,
            "git_ref": "main",
            "imported_commit": repository.commit.value,
        }
        assert len(bus_simulator.messages_per_routing_key.get(COMMIT_LOG_ROUTING_KEY, [])) == requests_before
