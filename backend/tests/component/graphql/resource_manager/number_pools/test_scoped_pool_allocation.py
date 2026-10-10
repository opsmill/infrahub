from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.graphql.initialization import prepare_graphql_params
from tests.adapters.lock.timeline import LockAction
from tests.helpers.graphql import graphql
from tests.helpers.number_pool import (
    SCOPED_DEVICE,
    SCOPED_POOL_SCHEMA,
    pool_lock_events,
    scoped_device,
    scoped_pool,
    scoped_site,
    vlan_id,
)
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.lock.timeline import LockTimeline


MOVE_DEVICE_AND_ALLOCATE = """
mutation MoveDeviceAndAllocate($device_id: String!, $site_id: String!, $pool_id: String!) {
    ScopeDeviceUpdate(data: {
        id: $device_id
        site: { id: $site_id }
        vlan_id: { value: null, from_pool: { id: $pool_id } }
    }) {
        ok
        object { vlan_id { value } }
    }
}
"""

ALLOCATE_IN_PLACE = """
mutation AllocateInPlace($device_id: String!, $pool_id: String!) {
    ScopeDeviceUpdate(data: {
        id: $device_id
        vlan_id: { value: null, from_pool: { id: $pool_id } }
    }) {
        ok
        object { vlan_id { value } }
    }
}
"""


@pytest.fixture
async def scoped_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The scoped pool test schema, saved on the default branch so that its fields hold the ids a scope stores."""
    await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool


@pytest.fixture
async def site_scoped_pool(db: InfrahubDatabase, scoped_schema: None) -> CoreNumberPool:
    return await scoped_pool(db=db, name="vlan-per-site", allocation_scope=["site"])


async def test_an_update_that_moves_a_device_allocates_in_the_new_site(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    device_a1 = await scoped_device(db=db, branch=default_branch, pool=site_scoped_pool, name="device-a1", site=site_a)
    for name in ("device-b1", "device-b2"):
        await scoped_device(db=db, branch=default_branch, pool=site_scoped_pool, name=name, site=site_b)
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    result = await graphql(
        schema=gql_params.schema,
        source=MOVE_DEVICE_AND_ALLOCATE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"device_id": device_a1.id, "site_id": site_b.id, "pool_id": site_scoped_pool.id},
    )

    assert result.errors is None
    assert result.data
    assert result.data["ScopeDeviceUpdate"]["object"]["vlan_id"]["value"] == 3
    stored = await NodeManager.get_one(db=db, branch=default_branch, id=device_a1.id, raise_on_error=True)
    assert vlan_id(stored) == 3


async def test_an_update_that_keeps_the_site_allocates_in_the_stored_site(
    db: InfrahubDatabase,
    default_branch: Branch,
    site_scoped_pool: CoreNumberPool,
    recording_lock_timeline: LockTimeline,
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    await scoped_device(db=db, branch=default_branch, pool=site_scoped_pool, name="device-a1", site=site_a)
    for name in ("device-b1", "device-b2"):
        await scoped_device(db=db, branch=default_branch, pool=site_scoped_pool, name=name, site=site_b)
    device_a2 = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=default_branch)
    await device_a2.new(db=db, name="device-a2", role="leaf", tags=["red"], site=site_a)
    await device_a2.save(db=db)
    expected_lock_name = f"resource_pool.{site_scoped_pool.id}.{site_a.id}"
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    start = recording_lock_timeline.checkpoint("write")

    result = await graphql(
        schema=gql_params.schema,
        source=ALLOCATE_IN_PLACE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"device_id": device_a2.id, "pool_id": site_scoped_pool.id},
    )

    assert result.errors is None
    assert result.data
    assert result.data["ScopeDeviceUpdate"]["object"]["vlan_id"]["value"] == 2
    stored = await NodeManager.get_one(db=db, branch=default_branch, id=device_a2.id, raise_on_error=True)
    assert vlan_id(stored) == 2
    assert pool_lock_events(timeline=recording_lock_timeline, pool=site_scoped_pool, after=start) == [
        (expected_lock_name, LockAction.ACQUIRE),
        (expected_lock_name, LockAction.RELEASE),
    ]
