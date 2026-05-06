from __future__ import annotations

from dataclasses import dataclass
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
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


@dataclass
class _BlockedBranchCase:
    """Parametrized case for a status that blocks mutations on the affected branch.

    When the URL branch is the blocked branch itself, the GraphQL middleware raises with
    `blocked_mutation_message`. When the URL branch is `main` (i.e. the inline checks inside
    BranchRebase / BranchMerge / ProposedChangeCreate are reached), each mutation has its own
    error wording — captured separately below.
    """

    name: str
    status: BranchStatus
    blocked_mutation_message: str
    rebase_message: str
    branch_merge_message: str
    proposed_change_create_message: str


_BLOCKED_BRANCH_CASES = [
    _BlockedBranchCase(
        name="merged",
        status=BranchStatus.MERGED,
        blocked_mutation_message="has been merged and is read-only",
        rebase_message="has been merged and is read-only",
        branch_merge_message="has already been merged",
        proposed_change_create_message="has been merged",
    ),
    _BlockedBranchCase(
        name="merging",
        # For MERGING, mutations against `main` hit the new default-branch lock check first
        # ("Branch 'main' is locked because branch '...' is currently being merged"). The
        # inline rebase/merge/proposed-change errors share the same "is currently being merged"
        # substring, so a single assertion satisfies both code paths.
        status=BranchStatus.MERGING,
        blocked_mutation_message="is currently being merged and is read-only",
        rebase_message="is currently being merged",
        branch_merge_message="is currently being merged",
        proposed_change_create_message="is currently being merged",
    ),
]


class TestMergedBranchStatus(TestInfrahubApp):
    """Behavioral tests for branches whose status blocks further mutations: MERGED and MERGING.

    Most checks fire from the same code path (BranchStatusChecker via the GraphQL middleware) so
    every case is parametrized over both statuses. The autouse cleanup fixture resets any
    non-OPEN, non-default branch back to OPEN after each test — otherwise a residual MERGING
    branch would lock `main` and break the next test's `client.branch.create(...)` call.
    """

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

    @pytest.fixture(autouse=True)
    async def _reset_non_open_branches(self, db: InfrahubDatabase) -> AsyncGenerator[None, None]:
        yield
        for branch in await Branch.get_list(db=db, exclude_default=True, exclude_global=True):
            if branch.status != BranchStatus.OPEN:
                branch.status = BranchStatus.OPEN
                await branch.save(db=db)

    @pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in _BLOCKED_BRANCH_CASES])
    async def test_blocked_branch_blocks_mutations(
        self,
        initial_dataset: None,
        client: InfrahubClient,
        db: InfrahubDatabase,
        car_person_schema_unique_owner: dict,
        case: _BlockedBranchCase,
    ) -> None:
        branch_name = f"blocks_mutations_{case.name}"
        branch = await client.branch.create(branch_name=branch_name)
        backend_branch = registry.branch[branch.name]
        backend_branch.status = case.status
        await backend_branch.save(db=db)

        # GraphQL mutation on the blocked branch
        node = await client.create(kind="TestingPerson", name=f"Person {case.name}", branch=branch_name)
        with pytest.raises(GraphQLError) as exc:
            await node.save()
        assert case.blocked_mutation_message in exc.value.message

        # REST schema load should also be blocked
        response = await client.schema.load([car_person_schema_unique_owner], branch=branch_name)
        assert response.errors
        assert case.blocked_mutation_message in str(response.errors)

    @pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in _BLOCKED_BRANCH_CASES])
    async def test_blocked_branch_allows_delete(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase, case: _BlockedBranchCase
    ) -> None:
        branch_name = f"allows_delete_{case.name}"
        branch = await client.branch.create(branch_name=branch_name)
        backend_branch = registry.branch[branch.name]
        backend_branch.status = case.status
        await backend_branch.save(db=db)

        # BranchDelete is on both allow-lists, so the middleware must not block it
        query = Mutation(
            mutation="BranchDelete",
            input_data={"data": {"name": branch.name}, "wait_until_completion": False},
            query={"ok": None, "task": {"id": None}},
        )
        result = await client.execute_graphql(query=query.render())
        assert result["BranchDelete"]["ok"] is True
        assert result["BranchDelete"]["task"]["id"]

    @pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in _BLOCKED_BRANCH_CASES])
    async def test_blocked_branch_blocks_rebase(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase, case: _BlockedBranchCase
    ) -> None:
        branch_name = f"blocks_rebase_{case.name}"
        branch = await client.branch.create(branch_name=branch_name)
        backend_branch = registry.branch[branch.name]
        backend_branch.status = case.status
        await backend_branch.save(db=db)

        query = Mutation(
            mutation="BranchRebase",
            input_data={"data": {"name": branch.name}, "wait_until_completion": False},
            query={"ok": None, "task": {"id": None}, "object": {"id": None}},
        )
        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=query.render())
        assert case.rebase_message in exc.value.message

    @pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in _BLOCKED_BRANCH_CASES])
    async def test_branch_merge_rejects_blocked_branch(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase, case: _BlockedBranchCase
    ) -> None:
        branch_name = f"branch_merge_blocked_{case.name}"
        branch = await client.branch.create(branch_name=branch_name)
        backend_branch = registry.branch[branch.name]
        backend_branch.status = case.status
        await backend_branch.save(db=db)

        query = Mutation(
            mutation="BranchMerge",
            input_data={"data": {"name": branch.name}, "wait_until_completion": False},
            query={"ok": None, "task": {"id": None}, "object": {"id": None}},
        )
        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=query.render())
        assert case.branch_merge_message in exc.value.message

    @pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in _BLOCKED_BRANCH_CASES])
    async def test_proposed_change_create_rejects_blocked_source_branch(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase, case: _BlockedBranchCase
    ) -> None:
        branch_name = f"proposed_change_blocked_{case.name}"
        branch = await client.branch.create(branch_name=branch_name)
        backend_branch = registry.branch[branch.name]
        backend_branch.status = case.status
        await backend_branch.save(db=db)

        query = Mutation(
            mutation="CoreProposedChangeCreate",
            input_data={
                "data": {
                    "name": {"value": f"PC {case.name}"},
                    "source_branch": {"value": branch_name},
                    "destination_branch": {"value": "main"},
                }
            },
            query={"ok": None, "object": {"id": None}},
        )
        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=query.render())
        assert case.proposed_change_create_message in exc.value.message

    async def test_merging_branch_locks_default_branch(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase
    ) -> None:
        """MERGING-only behavior: while any branch is MERGING the default branch is locked
        because it is the implicit merge target — mutations against `main` must be rejected."""
        branch_name = "locks_default_branch"
        branch = await client.branch.create(branch_name=branch_name)
        backend_branch = registry.branch[branch.name]
        backend_branch.status = BranchStatus.MERGING
        await backend_branch.save(db=db)

        node_on_main = await client.create(kind="TestingPerson", name="Main Writer", branch=registry.default_branch)
        with pytest.raises(GraphQLError) as exc:
            await node_on_main.save()
        assert "is locked because branch" in exc.value.message
        assert branch_name in exc.value.message


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
