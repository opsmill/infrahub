import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fast_depends import Provider

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.tasks import merge_branch
from infrahub.core.initialization import create_branch
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.workers.dependencies import build_database


class TestMergeTaskLock:
    """Verify the flow-level merge lock and the skip-if-not-open gate.

    `merge_branch` holds the global merge lock, loads the branch under it, and only runs the merge body
    (`_do_merge_branch`) for an OPEN branch. These tests substitute the body so they exercise the real
    lock + gate without running a full merge.
    """

    @pytest.fixture(autouse=True)
    async def _setup_core_schema(self, register_core_models_schema: SchemaBranch) -> None:
        return

    @pytest.fixture
    async def source_branch(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
    ) -> Branch:
        lock.initialize_lock(local_only=True)
        return await create_branch(branch_name="branch_1", db=db)

    @pytest.fixture
    async def second_source_branch(self, db: InfrahubDatabase, source_branch: Branch) -> Branch:
        return await create_branch(branch_name="branch_2", db=db)

    @pytest.fixture
    def context(self, default_branch: Branch) -> InfrahubContext:
        return InfrahubContext.init(
            branch=default_branch,
            account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
        )

    async def test_concurrent_merges_same_branch_only_execute_once(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        source_branch: Branch,
        dependency_provider: Provider,
        context: InfrahubContext,
    ) -> None:
        """When two merges of the same branch run concurrently, the merge body executes only once."""

        async def fake_merge_body(*, db: InfrahubDatabase, source_branch: Branch, **kwargs: Any) -> None:
            source_branch.status = BranchStatus.MERGED
            await source_branch.save(db=db)
            registry.branch[source_branch.name] = source_branch

        body_mock = AsyncMock(side_effect=fake_merge_body)

        with (
            dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
            patch("infrahub.core.branch.tasks._do_merge_branch", body_mock),
        ):
            await asyncio.gather(
                merge_branch(branch=source_branch.name, context=context),
                merge_branch(branch=source_branch.name, context=context),
            )

        body_mock.assert_awaited_once()

        merged_branch = await Branch.get_by_name(db=db, name=source_branch.name)
        assert merged_branch.status is BranchStatus.MERGED

    async def test_concurrent_merges_different_branches_both_execute_sequentially(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        source_branch: Branch,
        second_source_branch: Branch,
        dependency_provider: Provider,
        context: InfrahubContext,
    ) -> None:
        """When two merges of different branches run concurrently, both execute but not at the same time."""
        concurrent_count = 0
        max_concurrent = 0

        async def fake_merge_body(*, db: InfrahubDatabase, source_branch: Branch, **kwargs: Any) -> None:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.1)
            concurrent_count -= 1
            source_branch.status = BranchStatus.MERGED
            await source_branch.save(db=db)
            registry.branch[source_branch.name] = source_branch

        body_mock = AsyncMock(side_effect=fake_merge_body)

        with (
            dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
            patch("infrahub.core.branch.tasks._do_merge_branch", body_mock),
        ):
            await asyncio.gather(
                merge_branch(branch=source_branch.name, context=context),
                merge_branch(branch=second_source_branch.name, context=context),
            )

        assert body_mock.await_count == 2
        assert max_concurrent == 1

        merged_1 = await Branch.get_by_name(db=db, name=source_branch.name)
        assert merged_1.status is BranchStatus.MERGED
        merged_2 = await Branch.get_by_name(db=db, name=second_source_branch.name)
        assert merged_2.status is BranchStatus.MERGED
