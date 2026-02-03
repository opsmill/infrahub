from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.graphql import Mutation

from infrahub.core import registry
from infrahub.core.branch.enums import BranchStatus
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestMergedBranchStatus(TestInfrahubApp):
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

    async def test_merged_branch_blocks_mutations(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase, car_person_schema_unique_owner: dict
    ) -> None:
        branch_name = "merged_branch_test"
        branch = await client.branch.create(branch_name=branch_name)

        # Set status to MERGED (simulating post-merge state)
        backend_branch = registry.branch[branch.name]
        backend_branch.status = BranchStatus.MERGED
        await backend_branch.save(db=db)

        # Try any mutation on this branch - should fail
        node = await client.create(kind="TestingPerson", name="John Doe", branch=branch_name)
        with pytest.raises(GraphQLError) as exc:
            await node.save()

        assert "has been merged and is read-only" in exc.value.message

        # Schema loading should also be blocked
        with pytest.raises(ValueError) as exc:
            await client.schema.load([car_person_schema_unique_owner], branch=branch_name)
        assert "has been merged and is read-only" in str(exc.value)

    async def test_merged_branch_allows_delete(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase
    ) -> None:
        branch_name = "merged_branch_delete_test"
        branch = await client.branch.create(branch_name=branch_name)

        # Set status to MERGED
        backend_branch = registry.branch[branch.name]
        backend_branch.status = BranchStatus.MERGED
        await backend_branch.save(db=db)

        # We should still be able to delete the branch
        query = Mutation(
            mutation="BranchDelete",
            input_data={"data": {"name": branch.name}, "wait_until_completion": False},
            query={"ok": None, "task": {"id": None}},
        )
        result = await client.execute_graphql(query=query.render())
        assert result["BranchDelete"]["ok"] is True
        assert result["BranchDelete"]["task"]["id"]

    async def test_merged_branch_blocks_rebase(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase
    ) -> None:
        branch_name = "merged_branch_rebase_test"
        branch = await client.branch.create(branch_name=branch_name)

        # Set status to MERGED
        backend_branch = registry.branch[branch.name]
        backend_branch.status = BranchStatus.MERGED
        await backend_branch.save(db=db)

        # Rebase should be blocked on merged branches
        query = Mutation(
            mutation="BranchRebase",
            input_data={"data": {"name": branch.name}, "wait_until_completion": False},
            query={"ok": None, "task": {"id": None}, "object": {"id": None}},
        )
        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=query.render())

        assert "has been merged and is read-only" in exc.value.message

    async def test_branch_merge_rejects_already_merged_branch(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase
    ) -> None:
        branch_name = "already_merged_branch"
        branch = await client.branch.create(branch_name=branch_name)

        # Set status to MERGED
        backend_branch = registry.branch[branch.name]
        backend_branch.status = BranchStatus.MERGED
        await backend_branch.save(db=db)

        # BranchMerge should be rejected for already merged branches
        query = Mutation(
            mutation="BranchMerge",
            input_data={"data": {"name": branch.name}, "wait_until_completion": False},
            query={"ok": None, "task": {"id": None}, "object": {"id": None}},
        )
        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=query.render())

        assert "has already been merged" in exc.value.message

    async def test_proposed_change_create_rejects_merged_source_branch(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase
    ) -> None:
        branch_name = "merged_source_branch"
        branch = await client.branch.create(branch_name=branch_name)

        # Set status to MERGED
        backend_branch = registry.branch[branch.name]
        backend_branch.status = BranchStatus.MERGED
        await backend_branch.save(db=db)

        # ProposedChangeCreate should be rejected for merged source branches
        query = Mutation(
            mutation="CoreProposedChangeCreate",
            input_data={
                "data": {
                    "name": {"value": "Test PC"},
                    "source_branch": {"value": branch_name},
                    "destination_branch": {"value": "main"},
                }
            },
            query={"ok": None, "object": {"id": None}},
        )
        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=query.render())

        assert "has been merged" in exc.value.message


class TestNeedRebaseBranchStatus(TestInfrahubApp):
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

    async def test_need_rebase_branch_blocks_mutations(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase
    ) -> None:
        """Test that mutations are blocked on branches needing rebase."""
        branch_name = "need_rebase_branch_test"
        branch = await client.branch.create(branch_name=branch_name)

        # Set status to NEED_REBASE
        backend_branch = registry.branch[branch.name]
        backend_branch.status = BranchStatus.NEED_REBASE
        await backend_branch.save(db=db)

        # Try any mutation on this branch - should fail
        node = await client.create(kind="TestingPerson", name="Jane Doe", branch=branch_name)
        with pytest.raises(GraphQLError) as exc:
            await node.save()

        assert "must be rebased" in exc.value.message

    async def test_need_rebase_branch_allows_rebase(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase
    ) -> None:
        """Test that BranchRebase is allowed on branches needing rebase.

        This is the KEY DIFFERENCE from MERGED branches - rebase should work!
        """
        branch_name = "need_rebase_allows_rebase_test"
        branch = await client.branch.create(branch_name=branch_name)

        # Set status to NEED_REBASE
        backend_branch = registry.branch[branch.name]
        backend_branch.status = BranchStatus.NEED_REBASE
        await backend_branch.save(db=db)

        # BranchRebase should be allowed on branches needing rebase
        query = Mutation(
            mutation="BranchRebase",
            input_data={"data": {"name": branch.name}, "wait_until_completion": False},
            query={"ok": None, "task": {"id": None}, "object": {"id": None}},
        )
        result = await client.execute_graphql(query=query.render())
        assert result["BranchRebase"]["ok"] is True
        assert result["BranchRebase"]["task"]["id"]

    async def test_need_rebase_branch_allows_delete(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase
    ) -> None:
        """Test that BranchDelete is allowed on branches needing rebase."""
        branch_name = "need_rebase_delete_test"
        branch = await client.branch.create(branch_name=branch_name)

        # Set status to NEED_REBASE
        backend_branch = registry.branch[branch.name]
        backend_branch.status = BranchStatus.NEED_REBASE
        await backend_branch.save(db=db)

        # We should still be able to delete the branch
        query = Mutation(
            mutation="BranchDelete",
            input_data={"data": {"name": branch.name}, "wait_until_completion": False},
            query={"ok": None, "task": {"id": None}},
        )
        result = await client.execute_graphql(query=query.render())
        assert result["BranchDelete"]["ok"] is True
        assert result["BranchDelete"]["task"]["id"]
