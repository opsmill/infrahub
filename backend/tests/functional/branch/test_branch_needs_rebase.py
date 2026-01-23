from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.graphql import Mutation

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestNeedsRebaseStatus(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> None:
        await load_schema(db, schema=CAR_SCHEMA)

    async def test_branch_needs_rebase(
        self, initial_dataset: str, client: InfrahubClient, db: InfrahubDatabase, car_person_schema_unique_owner: dict
    ) -> None:
        branch_name = "branch_to_rebase"
        branch = await client.branch.create(branch_name=branch_name)

        # Set status to NEED_REBASE
        backend_branch = registry.branch[branch.name]
        backend_branch.status = BranchStatus.NEED_REBASE
        await backend_branch.save(db=db)

        # Try any mutation on this branch
        node = await client.create(kind="TestingPerson", name="John Doe", branch="branch_to_rebase")
        with pytest.raises(GraphQLError) as exc:
            await node.save()

        assert f"Branch {branch_name} must be rebased before any updates can be made" in exc.value.message

        with pytest.raises(ValueError) as exc:
            await client.schema.load([car_person_schema_unique_owner], branch=branch_name)
        assert f"Branch {branch_name} must be rebased before any updates can be made" in str(exc.value)

        # We should still be able to rebase the branch
        query = Mutation(
            mutation="BranchRebase",
            input_data={"data": {"name": branch.name}, "wait_until_completion": False},
            query={"ok": None, "task": {"id": None}, "object": {"id": None}},
        )
        result = await client.execute_graphql(query=query.render())
        assert result["BranchRebase"]["ok"] is True
        assert result["BranchRebase"]["object"]["id"] == branch.id
        assert result["BranchRebase"]["task"]["id"]

        # Check branch status is now OPEN
        branch_after = await Branch.get_by_name(name=branch_name, db=db)
        assert branch_after.branched_from is not None
        assert branch.branched_from != branch_after.branched_from
        assert branch_after.status == BranchStatus.OPEN

        # We should still be able to delete the branch
        query = Mutation(
            mutation="BranchDelete",
            input_data={"data": {"name": branch.name}, "wait_until_completion": False},
            query={"ok": None, "task": {"id": None}},
        )
        result = await client.execute_graphql(query=query.render())
        assert result["BranchDelete"]["ok"] is True
        assert result["BranchDelete"]["task"]["id"]
