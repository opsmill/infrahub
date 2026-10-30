from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub import config, lock
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.node.create import create_node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_locker import NumberPoolLock
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.scope import Division, DivisionElementPath
from tests.adapters.lock.timeline import LockAction
from tests.helpers.number_pool import (
    SCOPED_ATTRIBUTE_NAME,
    SCOPED_DEVICE,
    SCOPED_POOL_SCHEMA,
    add_pool_range,
    save_schema_kinds,
    scoped_device,
    scoped_pool,
    scoped_site,
    vlan_id,
)

from .helpers import DELETE_RANGE, execute, range_bounds

if TYPE_CHECKING:
    from graphql import ExecutionResult

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.lock import LockTimeline, RecordingLockRegistry

POOL_NAME = "vlan-per-site"
WAIT_TIMEOUT_SECONDS = 30

UPDATE_DEVICE_VLAN = f"""
mutation UpdateDeviceVlan($device_id: String!, $vlan_id: BigInt!) {{
    {SCOPED_DEVICE.kind}Update(data: {{ id: $device_id, {SCOPED_ATTRIBUTE_NAME}: {{ value: $vlan_id }} }}) {{
        ok
    }}
}}
"""


@dataclass
class TwoRangePool:
    """A pool scoped by site over 1-10 and 20-30, with two sites and the lock names a test watches."""

    pool: CoreNumberPool
    high_range: Node
    site_1: Node
    site_2: Node

    @property
    def shared_lock(self) -> str:
        return f"resource_pool.{self.pool.get_id()}:shared"

    @property
    def exclusive_lock(self) -> str:
        return f"resource_pool.{self.pool.get_id()}:exclusive"


async def _two_range_pool(db: InfrahubDatabase, branch: Branch, high_range_weight: int | None) -> TwoRangePool:
    await save_schema_kinds(db=db, schema=SCOPED_POOL_SCHEMA)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    pool = await scoped_pool(db=db, name=POOL_NAME, allocation_scope=["site"])
    high_range = await add_pool_range(db=db, pool=pool, start=20, end=30, weight=high_range_weight)
    return TwoRangePool(
        pool=pool,
        high_range=high_range,
        site_1=await scoped_site(db=db, branch=branch, name="site-1"),
        site_2=await scoped_site(db=db, branch=branch, name="site-2"),
    )


@pytest.fixture
async def high_range_first(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> TwoRangePool:
    """The pool allocates from 20-30 first, so a new device receives 20."""
    return await _two_range_pool(db=db, branch=default_branch, high_range_weight=10)


@pytest.fixture
async def low_range_first(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> TwoRangePool:
    """The pool allocates from 1-10 first, so a new device receives 1."""
    return await _two_range_pool(db=db, branch=default_branch, high_range_weight=None)


async def _create_device(db: InfrahubDatabase, branch: Branch, site: Node, vlan: dict[str, Any]) -> Node:
    # A session holds a single connection, which cannot serve two racing coroutines.
    async with db.start_session() as session_db:
        return await create_node(
            data=deepcopy(
                {
                    "name": {"value": f"device-{site.get_id()}"},
                    "tags": {"value": ["red"]},
                    "role": {"value": "leaf"},
                    "site": {"id": site.get_id()},
                    "vlan_id": vlan,
                }
            ),
            db=session_db,
            branch=branch,
            schema=session_db.schema.get(name=SCOPED_DEVICE.kind, branch=branch, duplicate=False),
        )


async def _run(db: InfrahubDatabase, branch: Branch, source: str, variables: dict[str, Any]) -> ExecutionResult:
    async with db.start_session() as session_db:
        return await execute(db=session_db, branch=branch, source=source, variables=variables)


async def _wait_until_waiting(timeline: LockTimeline, name: str) -> None:
    async def _poll() -> None:
        while timeline.waiting(name) != 1:  # noqa: ASYNC110
            await asyncio.sleep(0.01)

    await asyncio.wait_for(_poll(), timeout=WAIT_TIMEOUT_SECONDS)


def _held_refusal(ranges: str, label: str, value: int) -> str:
    return (
        f"Changing the ranges of the {POOL_NAME} pool to {ranges} would leave numbers it tracks outside every range: "
        f"{SCOPED_DEVICE.kind} '{label}' holds {value} on branch 'main'. Keep a range covering each of these numbers, "
        "or change those numbers first."
    )


async def test_a_range_deletion_waits_for_an_allocation_from_the_range_and_is_refused(
    db: InfrahubDatabase,
    default_branch: Branch,
    high_range_first: TwoRangePool,
    recording_lock_registry: RecordingLockRegistry,
) -> None:
    allocation_gate = recording_lock_registry.gate(high_range_first.shared_lock)
    allocation = asyncio.create_task(
        _create_device(
            db=db,
            branch=default_branch,
            site=high_range_first.site_1,
            vlan={"from_pool": {"id": high_range_first.pool.get_id()}},
        )
    )
    await allocation_gate.wait_reached()
    deletion = asyncio.create_task(
        _run(db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": high_range_first.high_range.id})
    )
    await _wait_until_waiting(timeline=recording_lock_registry.timeline, name=high_range_first.exclusive_lock)

    allocation_gate.release()
    device = await asyncio.wait_for(allocation, timeout=WAIT_TIMEOUT_SECONDS)
    result = await asyncio.wait_for(deletion, timeout=WAIT_TIMEOUT_SECONDS)

    assert vlan_id(device) == 20
    assert [error.message for error in result.errors or []] == [
        _held_refusal(ranges="1 - 10", label=await device.get_display_label(db=db), value=20)
    ]
    assert await range_bounds(db=db, pool_id=high_range_first.pool.get_id()) == [(1, 10), (20, 30)]


async def test_an_allocation_waits_for_a_range_deletion_and_draws_from_the_remaining_range(
    db: InfrahubDatabase,
    default_branch: Branch,
    high_range_first: TwoRangePool,
    recording_lock_registry: RecordingLockRegistry,
) -> None:
    deletion_gate = recording_lock_registry.gate(high_range_first.exclusive_lock)
    deletion = asyncio.create_task(
        _run(db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": high_range_first.high_range.id})
    )
    await deletion_gate.wait_reached()
    allocation = asyncio.create_task(
        _create_device(
            db=db,
            branch=default_branch,
            site=high_range_first.site_1,
            vlan={"from_pool": {"id": high_range_first.pool.get_id()}},
        )
    )
    await _wait_until_waiting(timeline=recording_lock_registry.timeline, name=high_range_first.shared_lock)

    deletion_gate.release()
    result = await asyncio.wait_for(deletion, timeout=WAIT_TIMEOUT_SECONDS)
    device = await asyncio.wait_for(allocation, timeout=WAIT_TIMEOUT_SECONDS)

    assert result.errors is None
    assert vlan_id(device) == 1
    assert await range_bounds(db=db, pool_id=high_range_first.pool.get_id()) == [(1, 10)]


async def test_an_allocation_in_another_division_completes_while_one_holds_the_pool(
    db: InfrahubDatabase,
    default_branch: Branch,
    high_range_first: TwoRangePool,
    recording_lock_registry: RecordingLockRegistry,
) -> None:
    pool_id = high_range_first.pool.get_id()
    site_1_gate = recording_lock_registry.gate(high_range_first.shared_lock)
    site_1_allocation = asyncio.create_task(
        _create_device(db=db, branch=default_branch, site=high_range_first.site_1, vlan={"from_pool": {"id": pool_id}})
    )
    await site_1_gate.wait_reached()

    site_2_device = await asyncio.wait_for(
        _create_device(db=db, branch=default_branch, site=high_range_first.site_2, vlan={"from_pool": {"id": pool_id}}),
        timeout=WAIT_TIMEOUT_SECONDS,
    )
    site_1_gate.release()
    site_1_device = await asyncio.wait_for(site_1_allocation, timeout=WAIT_TIMEOUT_SECONDS)

    assert vlan_id(site_2_device) == 20
    assert vlan_id(site_1_device) == 20


async def test_an_allocation_inside_a_transaction_holds_the_pool_until_the_commit(
    db: InfrahubDatabase,
    default_branch: Branch,
    high_range_first: TwoRangePool,
    recording_lock_timeline: LockTimeline,
) -> None:
    async with db.start_transaction() as dbt:
        await create_node(
            data={
                "name": {"value": "device-1"},
                "tags": {"value": ["red"]},
                "role": {"value": "leaf"},
                "site": {"id": high_range_first.site_1.get_id()},
                "vlan_id": {"from_pool": {"id": high_range_first.pool.get_id()}},
            },
            db=dbt,
            branch=default_branch,
            schema=dbt.schema.get(name=SCOPED_DEVICE.kind, branch=default_branch, duplicate=False),
        )
        recording_lock_timeline.checkpoint("allocated")
    recording_lock_timeline.checkpoint("committed")

    recording_lock_timeline.assert_held_at_checkpoint(high_range_first.shared_lock, "allocated")
    recording_lock_timeline.assert_not_held_at_checkpoint(high_range_first.shared_lock, "committed")


async def test_a_range_deletion_still_waiting_for_an_allocation_at_the_wait_limit_is_refused(
    db: InfrahubDatabase,
    default_branch: Branch,
    high_range_first: TwoRangePool,
    recording_lock_registry: RecordingLockRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config.SETTINGS.cache, "exclusive_lock_wait_secs", 1)
    allocation_gate = recording_lock_registry.gate(high_range_first.shared_lock)
    allocation = asyncio.create_task(
        _create_device(
            db=db,
            branch=default_branch,
            site=high_range_first.site_1,
            vlan={"from_pool": {"id": high_range_first.pool.get_id()}},
        )
    )
    await allocation_gate.wait_reached()

    result = await asyncio.wait_for(
        _run(db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": high_range_first.high_range.id}),
        timeout=WAIT_TIMEOUT_SECONDS,
    )
    allocation_gate.release()
    await asyncio.wait_for(allocation, timeout=WAIT_TIMEOUT_SECONDS)

    assert [error.message for error in result.errors or []] == [
        f"Numbers are still being allocated from the pool {POOL_NAME}; retry the change."
    ]
    assert recording_lock_registry.timeline.currently_held() == set()
    assert await range_bounds(db=db, pool_id=high_range_first.pool.get_id()) == [(1, 10), (20, 30)]


async def test_a_range_deletion_runs_while_an_allocation_waits_for_its_division(
    db: InfrahubDatabase,
    default_branch: Branch,
    high_range_first: TwoRangePool,
    recording_lock_registry: RecordingLockRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config.SETTINGS.cache, "exclusive_lock_wait_secs", 1)
    picking_lock = NumberPoolLock.picking_lock_name(
        pool_id=high_range_first.pool.get_id(), division_key=high_range_first.site_1.get_id()
    )
    picking_held = asyncio.Event()
    picking_release = asyncio.Event()

    async def hold_picking() -> None:
        async with lock.registry.get(name=picking_lock):
            picking_held.set()
            await asyncio.wait_for(picking_release.wait(), timeout=WAIT_TIMEOUT_SECONDS)

    device_schema = db.schema.get(name=SCOPED_DEVICE.kind, branch=default_branch, duplicate=False)
    site = device_schema.get_relationship(name="site")
    division = Division(
        elements=(DivisionElementPath(name=site.get_identifier(), relationship_direction=site.direction),),
        values=(high_range_first.site_1.get_id(),),
    )

    async def allocate() -> int:
        # Allocates without taking the division's lock first, as a template component does.
        async with db.start_session() as session_db:
            return await high_range_first.pool.get_resource(
                db=session_db,
                branch=default_branch,
                attribute=device_schema.get_attribute(name=SCOPED_ATTRIBUTE_NAME),
                identifier="component-allocation",
                division=division,
            )

    holder = asyncio.create_task(hold_picking())
    await asyncio.wait_for(picking_held.wait(), timeout=WAIT_TIMEOUT_SECONDS)
    allocation = asyncio.create_task(allocate())
    await _wait_until_waiting(timeline=recording_lock_registry.timeline, name=picking_lock)

    result = await asyncio.wait_for(
        _run(db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": high_range_first.high_range.id}),
        timeout=WAIT_TIMEOUT_SECONDS,
    )
    picking_release.set()
    await asyncio.wait_for(holder, timeout=WAIT_TIMEOUT_SECONDS)
    number = await asyncio.wait_for(allocation, timeout=WAIT_TIMEOUT_SECONDS)

    assert result.errors is None
    assert number == 1
    assert await range_bounds(db=db, pool_id=high_range_first.pool.get_id()) == [(1, 10)]


async def test_a_range_deletion_waits_for_a_number_attached_in_the_range_and_is_refused(
    db: InfrahubDatabase,
    default_branch: Branch,
    low_range_first: TwoRangePool,
    recording_lock_registry: RecordingLockRegistry,
) -> None:
    attach_gate = recording_lock_registry.gate(low_range_first.shared_lock)
    attach = asyncio.create_task(
        _create_device(
            db=db,
            branch=default_branch,
            site=low_range_first.site_1,
            vlan={"value": 25, "from_pool": {"id": low_range_first.pool.get_id()}},
        )
    )
    await attach_gate.wait_reached()
    deletion = asyncio.create_task(
        _run(db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": low_range_first.high_range.id})
    )
    await _wait_until_waiting(timeline=recording_lock_registry.timeline, name=low_range_first.exclusive_lock)

    attach_gate.release()
    device = await asyncio.wait_for(attach, timeout=WAIT_TIMEOUT_SECONDS)
    result = await asyncio.wait_for(deletion, timeout=WAIT_TIMEOUT_SECONDS)

    assert vlan_id(device) == 25
    assert [error.message for error in result.errors or []] == [
        _held_refusal(ranges="1 - 10", label=await device.get_display_label(db=db), value=25)
    ]


async def test_a_number_attached_after_a_range_deletion_it_waited_for_is_refused(
    db: InfrahubDatabase,
    default_branch: Branch,
    low_range_first: TwoRangePool,
    recording_lock_registry: RecordingLockRegistry,
) -> None:
    deletion_gate = recording_lock_registry.gate(low_range_first.exclusive_lock)
    deletion = asyncio.create_task(
        _run(db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": low_range_first.high_range.id})
    )
    await deletion_gate.wait_reached()
    attach = asyncio.create_task(
        _create_device(
            db=db,
            branch=default_branch,
            site=low_range_first.site_1,
            vlan={"value": 25, "from_pool": {"id": low_range_first.pool.get_id()}},
        )
    )
    await _wait_until_waiting(timeline=recording_lock_registry.timeline, name=low_range_first.shared_lock)

    deletion_gate.release()
    result = await asyncio.wait_for(deletion, timeout=WAIT_TIMEOUT_SECONDS)

    assert result.errors is None
    with pytest.raises(
        ValidationError,
        match=(
            rf"^The '{POOL_NAME}' pool cannot track 25 on '{SCOPED_ATTRIBUTE_NAME}', because 25 is outside its "
            rf"ranges: 1 - 10\. Choose a number inside those ranges\. at {SCOPED_ATTRIBUTE_NAME}\.from_pool$"
        ),
    ):
        await asyncio.wait_for(attach, timeout=WAIT_TIMEOUT_SECONDS)


async def test_a_range_deletion_waits_for_a_tracked_number_edited_into_the_range_and_is_refused(
    db: InfrahubDatabase,
    default_branch: Branch,
    low_range_first: TwoRangePool,
    recording_lock_registry: RecordingLockRegistry,
) -> None:
    device = await scoped_device(
        db=db, branch=default_branch, pool=low_range_first.pool, name="device-1", site=low_range_first.site_1
    )
    assert vlan_id(device) == 1
    edit_gate = recording_lock_registry.gate(low_range_first.shared_lock)
    edit = asyncio.create_task(
        _run(
            db=db,
            branch=default_branch,
            source=UPDATE_DEVICE_VLAN,
            variables={"device_id": device.get_id(), "vlan_id": 25},
        )
    )
    await edit_gate.wait_reached()
    deletion = asyncio.create_task(
        _run(db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": low_range_first.high_range.id})
    )
    await _wait_until_waiting(timeline=recording_lock_registry.timeline, name=low_range_first.exclusive_lock)

    edit_gate.release()
    edit_result = await asyncio.wait_for(edit, timeout=WAIT_TIMEOUT_SECONDS)
    deletion_result = await asyncio.wait_for(deletion, timeout=WAIT_TIMEOUT_SECONDS)

    assert edit_result.errors is None
    assert [error.message for error in deletion_result.errors or []] == [
        _held_refusal(ranges="1 - 10", label=await device.get_display_label(db=db), value=25)
    ]


async def test_a_tracked_number_edited_after_a_range_deletion_it_waited_for_is_refused(
    db: InfrahubDatabase,
    default_branch: Branch,
    low_range_first: TwoRangePool,
    recording_lock_registry: RecordingLockRegistry,
) -> None:
    device = await scoped_device(
        db=db, branch=default_branch, pool=low_range_first.pool, name="device-1", site=low_range_first.site_1
    )
    deletion_gate = recording_lock_registry.gate(low_range_first.exclusive_lock)
    deletion = asyncio.create_task(
        _run(db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": low_range_first.high_range.id})
    )
    await deletion_gate.wait_reached()
    edit = asyncio.create_task(
        _run(
            db=db,
            branch=default_branch,
            source=UPDATE_DEVICE_VLAN,
            variables={"device_id": device.get_id(), "vlan_id": 25},
        )
    )
    await _wait_until_waiting(timeline=recording_lock_registry.timeline, name=low_range_first.shared_lock)

    deletion_gate.release()
    deletion_result = await asyncio.wait_for(deletion, timeout=WAIT_TIMEOUT_SECONDS)
    edit_result = await asyncio.wait_for(edit, timeout=WAIT_TIMEOUT_SECONDS)

    assert deletion_result.errors is None
    assert [error.message for error in edit_result.errors or []] == [
        f"'{SCOPED_ATTRIBUTE_NAME}' is tracked by the '{POOL_NAME}' pool, so it cannot hold 25, which is outside the "
        f"pool's ranges: 1 - 10. Choose a number inside those ranges, or remove the '{POOL_NAME}' pool from "
        f"'{SCOPED_ATTRIBUTE_NAME}' in the same change that sets it to 25. at {SCOPED_ATTRIBUTE_NAME}.value"
    ]


async def test_two_range_changes_on_one_pool_run_one_after_the_other(
    db: InfrahubDatabase,
    default_branch: Branch,
    low_range_first: TwoRangePool,
    recording_lock_registry: RecordingLockRegistry,
) -> None:
    low_range_id = next(
        pool_range.get_id()
        for pool_range in await NumberPoolRepository(db=db).get_ranges(pool_id=low_range_first.pool.get_id())
        if pool_range.get_id() != low_range_first.high_range.get_id()
    )
    first_gate = recording_lock_registry.gate(low_range_first.exclusive_lock)
    first = asyncio.create_task(
        _run(db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": low_range_first.high_range.id})
    )
    await first_gate.wait_reached()
    second = asyncio.create_task(
        _run(db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": low_range_id})
    )
    await _wait_until_waiting(timeline=recording_lock_registry.timeline, name=low_range_first.exclusive_lock)

    first_gate.release()
    first_result = await asyncio.wait_for(first, timeout=WAIT_TIMEOUT_SECONDS)
    second_result = await asyncio.wait_for(second, timeout=WAIT_TIMEOUT_SECONDS)

    assert first_result.errors is None
    assert second_result.errors is None
    acquired = [
        event.name
        for event in recording_lock_registry.timeline.events
        if event.action is LockAction.ACQUIRE and event.name == low_range_first.exclusive_lock
    ]
    assert acquired == [low_range_first.exclusive_lock, low_range_first.exclusive_lock]
    assert await range_bounds(db=db, pool_id=low_range_first.pool.get_id()) == []
