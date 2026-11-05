from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

import pytest

from infrahub import lock
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.create import create_node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.pools.number_pool_locker import picking_lock_name
from infrahub.pools.scope import Division, DivisionElementPath
from tests.helpers.constants import LOCK_WAIT_TIMEOUT_SECONDS
from tests.helpers.number_pool import (
    SCOPED_ATTRIBUTE_NAME,
    SCOPED_DEVICE,
    SCOPED_POOL_SCHEMA,
    add_pool_range,
    save_schema_kinds,
    scoped_device_holding,
    scoped_pool,
    scoped_site,
    vlan_id,
)

from .helpers import DELETE_RANGE, execute_in_own_session, range_bounds

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from graphql import ExecutionResult

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.lock import LockTimeline, RecordingLockRegistry

pytestmark = pytest.mark.usefixtures("exclusive_lock_wait")

POOL_NAME = "vlan-per-site"
DEVICE_NAME = "device-1"

CREATE_DEVICE = f"""
mutation CreateDevice($data: {SCOPED_DEVICE.kind}CreateInput!) {{
    {SCOPED_DEVICE.kind}Create(data: $data) {{
        ok
    }}
}}
"""

UPDATE_DEVICE = f"""
mutation UpdateDevice($data: {SCOPED_DEVICE.kind}UpdateInput!) {{
    {SCOPED_DEVICE.kind}Update(data: $data) {{
        ok
    }}
}}
"""


@dataclass
class TwoRangePool:
    """A pool scoped by site over 1-10 and 20-30 that allocates from 20-30 first, and the lock names a test watches."""

    pool: CoreNumberPool
    high_range: Node
    site: Node

    @property
    def shared_lock(self) -> str:
        return f"resource_pool.{self.pool.get_id()}:shared"

    @property
    def exclusive_lock(self) -> str:
        return f"resource_pool.{self.pool.get_id()}:exclusive"


@pytest.fixture
async def two_range_pool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> TwoRangePool:
    await save_schema_kinds(db=db, schema=SCOPED_POOL_SCHEMA)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    pool = await scoped_pool(db=db, name=POOL_NAME, allocation_scope=["site"])
    high_range = await add_pool_range(db=db, pool=pool, start=20, end=30, weight=10)
    return TwoRangePool(
        pool=pool, high_range=high_range, site=await scoped_site(db=db, branch=default_branch, name="site-1")
    )


class RangeWrite(Enum):
    """A write that reads the pool's ranges."""

    ALLOCATE = "allocate"
    """Create a device that draws its number from the pool."""
    ATTACH = "attach"
    """Create a device that provides 25 for the pool to track."""
    EDIT = "edit"
    """Edit to 25 the number of a device that holds 1, which the pool tracks."""


@dataclass
class RangeWriteCase:
    name: str
    write: RangeWrite
    number_before_deletion: int
    """The number the write gives the device when it runs before the deletion of 20-30."""
    errors_after_deletion: list[str]
    numbers_after_deletion: list[int]
    """The numbers the devices hold when the write runs after the deletion of 20-30."""


RANGE_WRITE_CASES = [
    RangeWriteCase(
        name="allocation",
        write=RangeWrite.ALLOCATE,
        number_before_deletion=20,
        errors_after_deletion=[],
        numbers_after_deletion=[1],
    ),
    RangeWriteCase(
        name="attached-number",
        write=RangeWrite.ATTACH,
        number_before_deletion=25,
        errors_after_deletion=[
            f"The '{POOL_NAME}' pool cannot track 25 on '{SCOPED_ATTRIBUTE_NAME}', because 25 is outside its ranges: "
            f"1 - 10. Choose a number inside those ranges. at {SCOPED_ATTRIBUTE_NAME}.from_pool"
        ],
        numbers_after_deletion=[],
    ),
    RangeWriteCase(
        name="edited-number",
        write=RangeWrite.EDIT,
        number_before_deletion=25,
        errors_after_deletion=[
            f"'{SCOPED_ATTRIBUTE_NAME}' is tracked by the '{POOL_NAME}' pool, so it cannot hold 25, which is outside "
            f"the pool's ranges: 1 - 10. Choose a number inside those ranges, or remove the '{POOL_NAME}' pool from "
            f"'{SCOPED_ATTRIBUTE_NAME}' in the same change that sets it to 25. at {SCOPED_ATTRIBUTE_NAME}.value"
        ],
        numbers_after_deletion=[1],
    ),
]


def _new_device(two_range_pool: TwoRangePool, vlan: dict[str, Any]) -> dict[str, Any]:
    return {
        "data": {
            "name": {"value": DEVICE_NAME},
            "tags": {"value": ["red"]},
            "role": {"value": "leaf"},
            "site": {"id": two_range_pool.site.get_id()},
            SCOPED_ATTRIBUTE_NAME: vlan,
        }
    }


async def _prepare_write(
    db: InfrahubDatabase, branch: Branch, two_range_pool: TwoRangePool, write: RangeWrite
) -> tuple[str, dict[str, Any]]:
    """Return the mutation and the variables of the write."""
    from_pool = {"from_pool": {"id": two_range_pool.pool.get_id()}}
    match write:
        case RangeWrite.ALLOCATE:
            return CREATE_DEVICE, _new_device(two_range_pool=two_range_pool, vlan=from_pool)
        case RangeWrite.ATTACH:
            return CREATE_DEVICE, _new_device(two_range_pool=two_range_pool, vlan={"value": 25} | from_pool)
        case RangeWrite.EDIT:
            device = await scoped_device_holding(
                db=db, branch=branch, pool=two_range_pool.pool, name=DEVICE_NAME, site=two_range_pool.site, number=1
            )
            return UPDATE_DEVICE, {"data": {"id": device.get_id(), SCOPED_ATTRIBUTE_NAME: {"value": 25}}}


async def _device_numbers(db: InfrahubDatabase, branch: Branch) -> list[int]:
    devices = await NodeManager.query(db=db, schema=SCOPED_DEVICE.kind, branch=branch)
    return [vlan_id(device) for device in devices]


async def _wait_until_waiting(timeline: LockTimeline, name: str) -> None:
    async def _poll() -> None:
        while timeline.waiting(name) != 1:  # noqa: ASYNC110
            await asyncio.sleep(0.01)

    await asyncio.wait_for(_poll(), timeout=LOCK_WAIT_TIMEOUT_SECONDS)


async def _race(
    registry: RecordingLockRegistry,
    first: Coroutine[Any, Any, ExecutionResult],
    held_at: str,
    second: Coroutine[Any, Any, ExecutionResult],
    waits_at: str,
) -> tuple[ExecutionResult, ExecutionResult]:
    """Hold `first` once it takes the lock `held_at`, start `second`, and release `first` once `second` waits at `waits_at`."""
    gate = registry.gate(held_at)
    first_task = asyncio.create_task(first)
    await gate.wait_reached()
    second_task = asyncio.create_task(second)
    await _wait_until_waiting(timeline=registry.timeline, name=waits_at)

    gate.release()
    first_result = await asyncio.wait_for(first_task, timeout=LOCK_WAIT_TIMEOUT_SECONDS)
    second_result = await asyncio.wait_for(second_task, timeout=LOCK_WAIT_TIMEOUT_SECONDS)
    return first_result, second_result


def _errors(result: ExecutionResult) -> list[str]:
    return [error.message for error in result.errors or []]


@pytest.mark.parametrize("case", RANGE_WRITE_CASES, ids=[case.name for case in RANGE_WRITE_CASES])
async def test_a_range_deletion_waits_for_a_write_into_the_range_and_is_refused(
    db: InfrahubDatabase,
    default_branch: Branch,
    two_range_pool: TwoRangePool,
    recording_lock_registry: RecordingLockRegistry,
    case: RangeWriteCase,
) -> None:
    source, variables = await _prepare_write(
        db=db, branch=default_branch, two_range_pool=two_range_pool, write=case.write
    )

    write_result, deletion_result = await _race(
        registry=recording_lock_registry,
        first=execute_in_own_session(db=db, branch=default_branch, source=source, variables=variables),
        held_at=two_range_pool.shared_lock,
        second=execute_in_own_session(
            db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": two_range_pool.high_range.id}
        ),
        waits_at=two_range_pool.exclusive_lock,
    )

    assert _errors(write_result) == []
    assert _errors(deletion_result) == [
        f"Changing the ranges of the {POOL_NAME} pool to 1 - 10 would leave numbers it tracks outside every range: "
        f"{SCOPED_DEVICE.kind} '{DEVICE_NAME}' holds {case.number_before_deletion} on branch 'main'. Keep a range "
        "covering each of these numbers, or change those numbers first."
    ]
    assert await _device_numbers(db=db, branch=default_branch) == [case.number_before_deletion]
    assert await range_bounds(db=db, pool_id=two_range_pool.pool.get_id()) == [(1, 10), (20, 30)]


@pytest.mark.parametrize("case", RANGE_WRITE_CASES, ids=[case.name for case in RANGE_WRITE_CASES])
async def test_a_write_waits_for_a_range_deletion_and_reads_the_remaining_range(
    db: InfrahubDatabase,
    default_branch: Branch,
    two_range_pool: TwoRangePool,
    recording_lock_registry: RecordingLockRegistry,
    case: RangeWriteCase,
) -> None:
    source, variables = await _prepare_write(
        db=db, branch=default_branch, two_range_pool=two_range_pool, write=case.write
    )

    deletion_result, write_result = await _race(
        registry=recording_lock_registry,
        first=execute_in_own_session(
            db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": two_range_pool.high_range.id}
        ),
        held_at=two_range_pool.exclusive_lock,
        second=execute_in_own_session(db=db, branch=default_branch, source=source, variables=variables),
        waits_at=two_range_pool.shared_lock,
    )

    assert _errors(deletion_result) == []
    assert _errors(write_result) == case.errors_after_deletion
    assert await _device_numbers(db=db, branch=default_branch) == case.numbers_after_deletion
    assert await range_bounds(db=db, pool_id=two_range_pool.pool.get_id()) == [(1, 10)]


async def test_an_allocation_inside_a_transaction_holds_the_pool_until_the_commit(
    db: InfrahubDatabase,
    default_branch: Branch,
    two_range_pool: TwoRangePool,
    recording_lock_timeline: LockTimeline,
) -> None:
    async with db.start_transaction() as dbt:
        await create_node(
            data={
                "name": {"value": "device-1"},
                "tags": {"value": ["red"]},
                "role": {"value": "leaf"},
                "site": {"id": two_range_pool.site.get_id()},
                "vlan_id": {"from_pool": {"id": two_range_pool.pool.get_id()}},
            },
            db=dbt,
            branch=default_branch,
            schema=dbt.schema.get(name=SCOPED_DEVICE.kind, branch=default_branch, duplicate=False),
        )
        recording_lock_timeline.checkpoint("allocated")
    recording_lock_timeline.checkpoint("committed")

    recording_lock_timeline.assert_held_at_checkpoint(two_range_pool.shared_lock, "allocated")
    recording_lock_timeline.assert_not_held_at_checkpoint(two_range_pool.shared_lock, "committed")


async def test_a_range_deletion_still_waiting_for_an_allocation_at_the_wait_limit_is_refused(
    db: InfrahubDatabase,
    default_branch: Branch,
    two_range_pool: TwoRangePool,
    recording_lock_registry: RecordingLockRegistry,
    short_exclusive_lock_wait: None,
) -> None:
    source, variables = await _prepare_write(
        db=db, branch=default_branch, two_range_pool=two_range_pool, write=RangeWrite.ALLOCATE
    )
    allocation_gate = recording_lock_registry.gate(two_range_pool.shared_lock)
    allocation = asyncio.create_task(
        execute_in_own_session(db=db, branch=default_branch, source=source, variables=variables)
    )
    await allocation_gate.wait_reached()

    result = await asyncio.wait_for(
        execute_in_own_session(
            db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": two_range_pool.high_range.id}
        ),
        timeout=LOCK_WAIT_TIMEOUT_SECONDS,
    )
    allocation_gate.release()
    await asyncio.wait_for(allocation, timeout=LOCK_WAIT_TIMEOUT_SECONDS)

    assert _errors(result) == [f"Numbers are still being allocated from the pool {POOL_NAME}; retry the change."]
    assert recording_lock_registry.timeline.currently_held() == set()
    assert await range_bounds(db=db, pool_id=two_range_pool.pool.get_id()) == [(1, 10), (20, 30)]


async def test_a_range_deletion_runs_while_an_allocation_waits_for_its_division(
    db: InfrahubDatabase,
    default_branch: Branch,
    two_range_pool: TwoRangePool,
    recording_lock_registry: RecordingLockRegistry,
    short_exclusive_lock_wait: None,
) -> None:
    """A range change does not wait for an allocation still queued behind another one in the same division.

    That allocation then draws from the ranges left after the change; with the one-second wait limit, a range
    change that waited for it would be refused instead.
    """
    picking_lock = picking_lock_name(pool_id=two_range_pool.pool.get_id(), division_key=two_range_pool.site.get_id())
    picking_held = asyncio.Event()
    picking_release = asyncio.Event()

    async def hold_picking() -> None:
        async with lock.registry.get(name=picking_lock):
            picking_held.set()
            await asyncio.wait_for(picking_release.wait(), timeout=LOCK_WAIT_TIMEOUT_SECONDS)

    device_schema = db.schema.get(name=SCOPED_DEVICE.kind, branch=default_branch, duplicate=False)
    site = device_schema.get_relationship(name="site")
    division = Division(
        elements=(DivisionElementPath(name=site.get_identifier(), relationship_direction=site.direction),),
        values=(two_range_pool.site.get_id(),),
    )

    async def allocate() -> int:
        # Allocates without taking the division's lock first, as a template component does.
        async with db.start_session() as session_db:
            return await two_range_pool.pool.get_resource(
                db=session_db,
                branch=default_branch,
                attribute=device_schema.get_attribute(name=SCOPED_ATTRIBUTE_NAME),
                identifier="component-allocation",
                division=division,
            )

    holder = asyncio.create_task(hold_picking())
    await asyncio.wait_for(picking_held.wait(), timeout=LOCK_WAIT_TIMEOUT_SECONDS)
    allocation = asyncio.create_task(allocate())
    await _wait_until_waiting(timeline=recording_lock_registry.timeline, name=picking_lock)

    result = await asyncio.wait_for(
        execute_in_own_session(
            db=db, branch=default_branch, source=DELETE_RANGE, variables={"range_id": two_range_pool.high_range.id}
        ),
        timeout=LOCK_WAIT_TIMEOUT_SECONDS,
    )
    picking_release.set()
    await asyncio.wait_for(holder, timeout=LOCK_WAIT_TIMEOUT_SECONDS)
    number = await asyncio.wait_for(allocation, timeout=LOCK_WAIT_TIMEOUT_SECONDS)

    assert result.errors is None
    assert number == 1
    assert await range_bounds(db=db, pool_id=two_range_pool.pool.get_id()) == [(1, 10)]
