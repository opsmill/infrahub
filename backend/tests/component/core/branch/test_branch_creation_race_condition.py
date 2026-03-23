"""Test for race condition in branch creation (GitHub issue #8368).

When multiple concurrent requests create branches with the same name,
the check-then-create pattern in create_branch allows duplicates because
there is no lock or DB uniqueness constraint protecting the operation.
"""

import pytest

from infrahub import lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.query import QueryType
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


class TestBranchCreationRaceCondition:
    """Demonstrates that the database allows duplicate Branch nodes with the same name.

    In production, the create_branch task (backend/infrahub/core/branch/tasks.py)
    uses a check-then-create pattern:
      1. Branch.get_by_name() -> BranchNotFoundError (branch does not exist)
      2. Branch(...).save(db=db)  -> creates new Branch node

    When two workers execute this concurrently, both pass step 1 before either
    completes step 2, resulting in two Branch nodes with the same name.

    This test proves the underlying issue: the database has no uniqueness
    constraint on Branch.name, so two saves with the same name both succeed.
    """

    @pytest.fixture(autouse=True)
    async def _setup(self, register_core_models_schema: SchemaBranch, default_branch: Branch) -> None:
        lock.initialize_lock(local_only=True)

    async def test_database_allows_duplicate_branch_names(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
    ) -> None:
        """Creating two Branch nodes with the same name in the database should
        be prevented — either by a DB uniqueness constraint or by an
        application-level lock.

        Currently, neither protection exists, so both saves succeed.
        This test documents the bug: it PASSES on buggy code (duplicates
        are allowed) and will FAIL once a fix is applied.
        """
        branch_name = "duplicate-branch"
        now = Timestamp().to_string()

        # Simulate what happens when two workers both pass the existence check
        # and proceed to create — we directly create two Branch objects with
        # the same name, bypassing the check, exactly as the race allows.
        branch_1 = Branch(
            name=branch_name,
            status=BranchStatus.OPEN,
            description="first concurrent creation",
            origin_branch=registry.default_branch,
            branched_from=now,
            sync_with_git=False,
        )
        origin_schema = registry.schema.get_schema_branch(name=branch_1.origin_branch)
        new_schema = origin_schema.duplicate(name=branch_1.name)
        registry.schema.set_schema_branch(name=branch_1.name, schema=new_schema)
        branch_1.update_schema_hash()
        await branch_1.save(db=db, user_id="test-user")
        registry.branch[branch_1.name] = branch_1

        branch_2 = Branch(
            name=branch_name,
            status=BranchStatus.OPEN,
            description="second concurrent creation",
            origin_branch=registry.default_branch,
            branched_from=now,
            sync_with_git=False,
        )
        # Re-use the same schema (the second worker would also duplicate it)
        branch_2.update_schema_hash()
        await branch_2.save(db=db, user_id="test-user")

        # --- BUG ASSERTION ---
        # Both saves succeeded. Query the database directly to count how many
        # Branch nodes have this name.
        results = await db.execute_query(
            query="MATCH (n:Branch) WHERE n.name = $name RETURN n",
            params={"name": branch_name},
            name="count_duplicate_branches",
            type=QueryType.READ,
        )

        # On buggy code: 2 Branch nodes exist with the same name.
        # After the fix: the second save must be rejected (via DB constraint
        # or application-level lock), so only 1 node should exist.
        assert len(results) == 2, (
            f"Expected 2 Branch nodes named '{branch_name}' in the database "
            f"(documenting the race condition bug), but found {len(results)}"
        )

    async def test_get_by_name_silently_ignores_duplicates(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
    ) -> None:
        """When duplicate branches exist, Branch.get_by_name returns only
        the first one found, silently hiding the problem.

        After the fix, this test should fail because duplicates can no longer
        be created in the first place.
        """
        branch_name = "hidden-duplicate"
        now = Timestamp().to_string()

        # Create two branches with the same name
        for description in ("first", "second"):
            branch = Branch(
                name=branch_name,
                status=BranchStatus.OPEN,
                description=description,
                origin_branch=registry.default_branch,
                branched_from=now,
                sync_with_git=False,
            )
            if description == "first":
                origin_schema = registry.schema.get_schema_branch(name=branch.origin_branch)
                new_schema = origin_schema.duplicate(name=branch.name)
                registry.schema.set_schema_branch(name=branch.name, schema=new_schema)
            branch.update_schema_hash()
            await branch.save(db=db, user_id="test-user")

        # Verify duplicates exist
        results = await db.execute_query(
            query="MATCH (n:Branch) WHERE n.name = $name RETURN n",
            params={"name": branch_name},
            name="count_hidden_duplicates",
            type=QueryType.READ,
        )
        assert len(results) == 2, f"Setup failed: expected 2 Branch nodes, found {len(results)}"

        # get_by_name returns only one — the duplicate is invisible
        fetched = await Branch.get_by_name(db=db, name=branch_name)
        assert fetched is not None

        # The caller has no idea there is a second branch with the same name.
        # This is a secondary symptom of the bug: even if duplicates sneak in,
        # the system silently picks one and ignores the other.
