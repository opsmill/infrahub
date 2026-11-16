"""The synchronizer reports a pool whose change it could not apply and still processes the other pools."""

from __future__ import annotations

import asyncio
import copy
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.pools.number_pool_locker import RESOURCE_POOL_LOCK_NAMESPACE
from infrahub.pools.number_pool_repository import NumberPoolRepository
from tests.component.pools.schema_number_pool_synchronizer.helpers import (
    COUNTER_KIND,
    counter_schema,
    create_device_pool,
    default_device,
    provision_pool,
    run_synchronizer,
    stored_scope_of,
)
from tests.helpers.constants import LOCK_WAIT_TIMEOUT_SECONDS
from tests.helpers.number_pool import SCOPED_DEVICE, SCOPED_POOL_SCHEMA
from tests.helpers.schema import save_schema

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@asynccontextmanager
async def held_by_a_write(pool_id: str) -> AsyncGenerator[None]:
    """Hold the pool in shared mode from another task, as a write reading its ranges does, until the block exits."""
    held = asyncio.Event()
    release = asyncio.Event()

    async def hold() -> None:
        async with lock.registry.get_shared(name=pool_id, namespace=RESOURCE_POOL_LOCK_NAMESPACE).shared():
            held.set()
            await asyncio.wait_for(release.wait(), timeout=LOCK_WAIT_TIMEOUT_SECONDS)

    holder = asyncio.create_task(hold())
    await asyncio.wait_for(held.wait(), timeout=LOCK_WAIT_TIMEOUT_SECONDS)
    try:
        yield
    finally:
        release.set()
        await asyncio.wait_for(holder, timeout=LOCK_WAIT_TIMEOUT_SECONDS)


async def pool_name_of(db: InfrahubDatabase, pool_id: str) -> str:
    pool = await NodeManager.get_one(db=db, id=pool_id, kind=CoreNumberPool, branch_agnostic=True)
    assert pool is not None
    return pool.name.value


def retry_refusal(pool_name: str) -> str:
    return f"Numbers are still being allocated from the pool {pool_name}; retry the change."


async def test_a_range_change_to_a_pool_held_by_a_write_is_reported_and_the_other_pools_are_provisioned(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    short_exclusive_lock_wait: None,
) -> None:
    pool_id = await provision_pool(
        db=db, branch=default_branch, parameters=NumberPoolParameters(start_range=1, end_range=100)
    )
    registry.schema.register_schema(
        schema=counter_schema(parameters=NumberPoolParameters(start_range=1, end_range=50)), branch=default_branch.name
    )
    ticket_schema = copy.deepcopy(counter_schema(parameters=NumberPoolParameters(start_range=1, end_range=10)))
    ticket_schema.nodes[0].name = "Ticket"
    ticket_branch = await create_branch(db=db, branch_name="ticket-pool")
    registry.schema.register_schema(schema=ticket_schema, branch=ticket_branch.name)

    async with held_by_a_write(pool_id=pool_id):
        result = await run_synchronizer(db=db)

    ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)
    ticket_pools = await NodeManager.query(
        db=db, schema=CoreNumberPool, filters={"node__value": "TestingTicket"}, branch_agnostic=True
    )
    assert result.refused_changes == [
        f"{COUNTER_KIND}.counter: {retry_refusal(pool_name=await pool_name_of(db=db, pool_id=pool_id))}"
    ]
    assert [(item.start.value, item.end.value) for item in ranges] == [(1, 100)]
    assert len(ticket_pools) == 1
    assert result.updated_branches == {ticket_branch.name}


async def test_a_pool_already_matching_its_declaration_is_left_alone_while_a_write_holds_it(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    short_exclusive_lock_wait: None,
) -> None:
    pool_id = await provision_pool(
        db=db, branch=default_branch, parameters=NumberPoolParameters(start_range=1, end_range=100)
    )

    async with held_by_a_write(pool_id=pool_id):
        result = await run_synchronizer(db=db)

    ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)
    assert result.refused_changes == []
    assert [(item.start.value, item.end.value) for item in ranges] == [(1, 100)]


async def test_a_scope_rename_on_a_pool_held_by_a_write_is_reported_and_the_other_pools_are_renamed(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    short_exclusive_lock_wait: None,
) -> None:
    await save_schema(db=db, schema=SCOPED_POOL_SCHEMA)
    held_pool_id = await create_device_pool(db=db, name="vlan-per-site", scope=["site"])
    free_pool_id = await create_device_pool(db=db, name="vlan-per-site-again", scope=["site"])
    device = default_device()
    site_id = device.get_relationship(name="site").id
    device.get_relationship(name="site").name = "location"
    await save_schema(db=db, schema=SchemaRoot(nodes=[device]))

    async with held_by_a_write(pool_id=held_pool_id):
        result = await run_synchronizer(db=db)

    assert result.refused_changes == [f"{SCOPED_DEVICE.kind}.vlan_id: {retry_refusal(pool_name='vlan-per-site')}"]
    assert await stored_scope_of(db=db, pool_id=held_pool_id) == [{"id": site_id, "name": "site"}]
    assert await stored_scope_of(db=db, pool_id=free_pool_id) == [{"id": site_id, "name": "location"}]
