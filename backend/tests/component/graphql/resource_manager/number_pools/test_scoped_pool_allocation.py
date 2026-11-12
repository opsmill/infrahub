from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.graphql.initialization import prepare_graphql_params
from tests.adapters.lock.timeline import LockAction
from tests.helpers.graphql import graphql
from tests.helpers.number_pool import (
    SCOPED_DEVICE,
    SCOPED_POOL_SCHEMA,
    pool_lock_events,
    save_schema_kinds,
    scoped_device,
    scoped_pool,
    scoped_site,
    vlan_id,
)

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

ADD_PROFILE_AND_ALLOCATE = """
mutation AddProfileAndAllocate($device_id: String!, $profile_ids: [RelatedNodeInput], $pool_id: String!) {
    ScopeDeviceUpdate(data: {
        id: $device_id
        profiles: $profile_ids
        vlan_id: { value: null, from_pool: { id: $pool_id } }
    }) {
        ok
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
    await save_schema_kinds(db=db, schema=SCOPED_POOL_SCHEMA)
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


@dataclass
class ProfileChangeCase:
    name: str
    element: str
    first_profile: dict[str, Any]
    second_profile: dict[str, Any]
    payload: dict[str, Any]


PROFILE_CHANGE_CASES = [
    ProfileChangeCase(
        name="site",
        element="site",
        first_profile={"site": "site-a"},
        second_profile={"site": "site-b"},
        payload={"role": {"value": "leaf"}},
    ),
    ProfileChangeCase(
        name="role",
        element="role",
        first_profile={"role": "leaf"},
        second_profile={"role": "spine"},
        payload={"site": "site-a"},
    ),
]


@pytest.mark.parametrize("case", PROFILE_CHANGE_CASES, ids=[case.name for case in PROFILE_CHANGE_CASES])
async def test_an_update_that_adds_a_profile_and_allocates_saves_the_profile_value(
    db: InfrahubDatabase, default_branch: Branch, scoped_schema: None, case: ProfileChangeCase
) -> None:
    """The second profile wins over the first, and the device keeps the value it gives after the save."""
    sites = {name: await scoped_site(db=db, branch=default_branch, name=name) for name in ("site-a", "site-b")}
    pool = await scoped_pool(db=db, name=f"vlan-per-{case.element}", allocation_scope=[case.element])
    profiles = []
    for name, priority, values in (("first", 2000, case.first_profile), ("second", 1000, case.second_profile)):
        profile = await Node.init(db=db, schema=f"Profile{SCOPED_DEVICE.kind}", branch=default_branch)
        await profile.new(
            db=db,
            profile_name=f"{name}-profile",
            profile_priority=priority,
            **{key: sites.get(value, value) for key, value in values.items()},
        )
        await profile.save(db=db)
        profiles.append(profile)
    payload = {key: {"id": sites[value].id} if isinstance(value, str) else value for key, value in case.payload.items()}
    device = await create_node(
        data={
            "name": {"value": "device-1"},
            "tags": {"value": ["red"]},
            "vlan_id": {"from_pool": {"id": pool.id}},
            "profiles": [{"id": profiles[0].id}],
            **payload,
        },
        db=db,
        branch=default_branch,
        schema=db.schema.get(name=SCOPED_DEVICE.kind, branch=default_branch, duplicate=False),
    )
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    result = await graphql(
        schema=gql_params.schema,
        source=ADD_PROFILE_AND_ALLOCATE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "device_id": device.id,
            "profile_ids": [{"id": profile.id} for profile in profiles],
            "pool_id": pool.id,
        },
    )

    assert result.errors is None
    stored = await NodeManager.get_one(db=db, branch=default_branch, id=device.id, raise_on_error=True)
    if case.element == "site":
        stored_site = await stored.get_relationship("site").get_peer(db=db)
        assert stored_site is not None
        assert stored_site.id == sites["site-b"].id
    else:
        assert stored.get_attribute("role").value == "spine"
