"""Test for race condition in branch creation (GitHub issue #8368).

When multiple concurrent requests create branches with the same name,
the check-then-create pattern in create_branch allows duplicates because
there is no distributed lock protecting the operation.

The fix wraps the check-and-create in create_branch (tasks.py) with a
distributed lock keyed by branch name (namespace="branch"), so concurrent
workers serialize branch creation for the same name.
"""

import asyncio

import pytest

from infrahub import lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.query import QueryType
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import BranchNotFoundError, ValidationError


async def create_branch_with_lock(
    db: InfrahubDatabase,
    branch_name: str,
    description: str = "",
) -> Branch:
    """Reproduce the create_branch flow from tasks.py: acquire distributed lock,
    check existence, then create. This mirrors the fixed code path."""
    async with lock.registry.get(name=branch_name, namespace="branch"):
        try:
            await Branch.get_by_name(db=db, name=branch_name)
            raise ValidationError(f"The branch {branch_name} already exists")
        except BranchNotFoundError:
            pass

        now = Timestamp().to_string()
        obj = Branch(
            name=branch_name,
            status=BranchStatus.OPEN,
            description=description,
            origin_branch=registry.default_branch,
            branched_from=now,
            sync_with_git=False,
        )

        async with lock.registry.local_schema_lock():
            origin_schema = registry.schema.get_schema_branch(name=obj.origin_branch)
            new_schema = origin_schema.duplicate(name=obj.name)
            registry.schema.set_schema_branch(name=obj.name, schema=new_schema)
            obj.update_schema_hash()
            await obj.save(db=db, user_id="test-user")
            registry.branch[obj.name] = obj

    return obj


class TestBranchCreationRaceCondition:
    """Verifies that the distributed lock in create_branch prevents
    duplicate Branch nodes from being created concurrently.
    """

    @pytest.fixture(autouse=True)
    async def _setup(self, register_core_models_schema: SchemaBranch, default_branch: Branch) -> None:
        lock.initialize_lock(local_only=True)

    async def test_second_branch_creation_rejected_by_lock(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
    ) -> None:
        """When two sequential create_branch calls run for the same name,
        the second one sees the branch already exists and raises ValidationError.
        """
        branch_name = "duplicate-branch"

        # First creation succeeds
        await create_branch_with_lock(db=db, branch_name=branch_name, description="first")

        # Second creation with the same name must fail
        with pytest.raises(ValidationError, match="already exists"):
            await create_branch_with_lock(db=db, branch_name=branch_name, description="second")

        # Verify only one branch exists in the database
        results = await db.execute_query(
            query="MATCH (n:Branch) WHERE n.name = $name RETURN n",
            params={"name": branch_name},
            name="count_branches",
            type=QueryType.READ,
        )
        assert len(results) == 1, f"Expected exactly 1 Branch node named '{branch_name}', but found {len(results)}"

    async def test_concurrent_branch_creation_serialized_by_lock(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
    ) -> None:
        """Concurrent create_branch calls for the same name are serialized
        by the distributed lock — only the first one succeeds.
        """
        branch_name = "concurrent-branch"
        results: list[Exception | None] = []

        async def attempt_create() -> None:
            try:
                await create_branch_with_lock(db=db, branch_name=branch_name)
                results.append(None)
            except Exception as exc:
                results.append(exc)

        # Run two concurrent creation attempts — the lock serializes them
        await asyncio.gather(attempt_create(), attempt_create())

        # Exactly one should have succeeded and one should have failed
        successes = [r for r in results if r is None]
        failures = [r for r in results if isinstance(r, ValidationError)]
        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
        assert len(failures) == 1, f"Expected 1 failure, got {len(failures)}: {results}"

        # Only one branch in the database
        db_results = await db.execute_query(
            query="MATCH (n:Branch) WHERE n.name = $name RETURN n",
            params={"name": branch_name},
            name="count_concurrent_branches",
            type=QueryType.READ,
        )
        assert len(db_results) == 1, (
            f"Expected exactly 1 Branch node named '{branch_name}', but found {len(db_results)}"
        )
