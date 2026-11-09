"""The branch the merging worker caches while a merge saves the source branch's status."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Self
from uuid import uuid4

import pytest
from pydantic import PrivateAttr

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.merge.builder import build_branch_merge_orchestrator
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.dependencies.registry import get_component_registry
from infrahub.tasks.registry import refresh_branches
from infrahub.workers.dependencies import build_event_service
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.dependency_override import override_dependency

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fast_depends import Provider

    from infrahub.database import InfrahubDatabase
    from tests.helpers.paused_branch_list import PausedBranchList


class BranchSavingMergedAfterAHook(Branch):
    """A branch that awaits a hook before it saves the merged status."""

    _before_merged_save: Callable[[], Awaitable[None]] = PrivateAttr()

    @classmethod
    def get_type(cls) -> str:
        return Branch.get_type()

    @classmethod
    def from_branch(cls, branch: Branch, before_merged_save: Callable[[], Awaitable[None]]) -> Self:
        hooked = cls.model_validate(branch.model_dump())
        hooked._before_merged_save = before_merged_save
        return hooked

    async def save(self, db: InfrahubDatabase, user_id: str = SYSTEM_USER_ID) -> bool:
        if self.status is BranchStatus.MERGED:
            await self._before_merged_save()
        return await super().save(db=db, user_id=user_id)


async def _fail_to_save() -> None:
    raise RuntimeError("saving the merged status failed")


async def _branch_with_a_change(db: InfrahubDatabase, default_branch: Branch, name: str) -> Branch:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="Alice", height=170)
    await person.save(db=db)

    branch = await create_branch(db=db, branch_name=name)
    person_on_branch = await NodeManager.get_one(db=db, id=person.id, branch=branch, raise_on_error=True)
    person_on_branch.get_attribute("height").value = 200
    await person_on_branch.save(db=db)

    diff_coordinator = await get_component_registry().get_component(DiffCoordinator, db=db, branch=branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    return branch


async def _merge(db: InfrahubDatabase, source_branch: Branch, dependency_provider: Provider) -> None:
    destination_branch = await registry.get_branch(db=db, branch=registry.default_branch)
    context = InfrahubContext.init(
        branch=destination_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )
    event_service = MemoryInfrahubEvent()
    with override_dependency(build_event_service, lambda: event_service, dependency_provider=dependency_provider):
        orchestrator = await build_branch_merge_orchestrator(
            db=db, source_branch=source_branch, destination_branch=destination_branch
        )
        await orchestrator.merge(context=context)


@pytest.mark.usefixtures("memory_cache", "workflow_recorder", "register_core_models_schema", "car_person_schema")
async def test_merge_keeps_the_merged_branch_cached_through_a_registry_refresh_that_read_it_merging(
    db: InfrahubDatabase,
    default_branch: Branch,
    dependency_provider: Provider,
    paused_branch_list: PausedBranchList,
) -> None:
    branch = await _branch_with_a_change(db=db, default_branch=default_branch, name="merged-during-refresh")
    refreshes: list[asyncio.Task[None]] = []

    async with db.start_session() as refresh_db:

        async def start_a_refresh() -> None:
            refreshes.append(asyncio.create_task(refresh_branches(db=refresh_db)))
            await asyncio.wait_for(paused_branch_list.read.wait(), timeout=30)

        source_branch = BranchSavingMergedAfterAHook.from_branch(
            await Branch.get_by_name(db=db, name=branch.name), before_merged_save=start_a_refresh
        )
        try:
            await asyncio.wait_for(
                _merge(db=db, source_branch=source_branch, dependency_provider=dependency_provider), timeout=120
            )
        finally:
            paused_branch_list.resume.set()
        await asyncio.wait_for(asyncio.gather(*refreshes), timeout=30)

    assert len(refreshes) == 1
    assert registry.branch[branch.name].status is BranchStatus.MERGED


@pytest.mark.usefixtures("memory_cache", "workflow_recorder", "register_core_models_schema", "car_person_schema")
async def test_merge_that_fails_to_save_the_merged_status_leaves_the_cached_branch_merging(
    db: InfrahubDatabase,
    default_branch: Branch,
    dependency_provider: Provider,
) -> None:
    branch = await _branch_with_a_change(db=db, default_branch=default_branch, name="merged-status-not-saved")
    source_branch = BranchSavingMergedAfterAHook.from_branch(
        await Branch.get_by_name(db=db, name=branch.name), before_merged_save=_fail_to_save
    )

    with pytest.raises(RuntimeError, match=r"^saving the merged status failed$"):
        await _merge(db=db, source_branch=source_branch, dependency_provider=dependency_provider)

    saved_branch = await Branch.get_by_name(db=db, name=branch.name)
    assert saved_branch.status is BranchStatus.MERGING
    assert registry.branch[branch.name].status is BranchStatus.MERGING
