from __future__ import annotations

import asyncio
import re
from copy import deepcopy
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RelationshipDirection
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.pools.scope import Division, DivisionElementPath
from tests.adapters.lock.timeline import LockAction
from tests.helpers.number_pool import (
    SCOPED_ATTRIBUTE_NAME,
    SCOPED_DEVICE,
    SCOPED_POOL_SCHEMA,
    SCOPED_SITE,
    add_pool_range,
    pool_lock_events,
    scoped_device,
    scoped_device_holding,
    scoped_pool,
    scoped_site,
    stored_scope,
    vlan_id,
)
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.lock.timeline import LockTimeline


def device_payload(name: str, site: Node, pool: CoreNumberPool, role: str | None = "leaf") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": {"value": name},
        "tags": {"value": ["red"]},
        "site": {"id": site.id},
        "vlan_id": {"from_pool": {"id": pool.id}},
    }
    if role is not None:
        payload["role"] = {"value": role}
    return payload


async def create_device_in_own_session(db: InfrahubDatabase, branch: Branch, payload: dict[str, Any]) -> Node:
    # A session holds a single connection, which cannot serve two racing coroutines.
    async with db.start_session() as session_db:
        return await create_node(
            data=deepcopy(payload),
            db=session_db,
            branch=branch,
            schema=session_db.schema.get(name=SCOPED_DEVICE.kind, branch=branch, duplicate=False),
        )


@pytest.fixture
async def templated_scoped_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The scoped pool test schema with an object template generated for the device."""
    schema = deepcopy(SCOPED_POOL_SCHEMA)
    next(node for node in schema.nodes if node.kind == SCOPED_DEVICE.kind).generate_template = True
    await load_schema(db=db, schema=schema, update_db=True)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool


@pytest.fixture
async def site_default_filter_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The scoped pool test schema with a site that a write can name by its name as a default filter value."""
    schema = deepcopy(SCOPED_POOL_SCHEMA)
    next(node for node in schema.nodes if node.kind == SCOPED_SITE.kind).default_filter = "name__value"
    await load_schema(db=db, schema=schema, update_db=True)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool


async def test_devices_of_two_sites_each_receive_the_first_number(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")

    device_a1 = await scoped_device(db=db, branch=default_branch, pool=site_scoped_pool, name="device-a1", site=site_a)
    device_b1 = await scoped_device(db=db, branch=default_branch, pool=site_scoped_pool, name="device-b1", site=site_b)
    device_a2 = await scoped_device(db=db, branch=default_branch, pool=site_scoped_pool, name="device-a2", site=site_a)

    assert (vlan_id(device_a1), vlan_id(device_b1), vlan_id(device_a2)) == (1, 1, 2)


async def test_a_node_asking_its_scoped_pool_again_gets_its_reserved_number(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    """Asking the pool again for a node retrieves the reservation it holds in its division, not a new number."""
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    await scoped_device(db=db, branch=default_branch, pool=site_scoped_pool, name="device-a1", site=site_a)
    device_b1 = await scoped_device(db=db, branch=default_branch, pool=site_scoped_pool, name="device-b1", site=site_b)
    attribute = device_b1.get_attribute(SCOPED_ATTRIBUTE_NAME)
    division_b = Division(
        elements=(DivisionElementPath(name="scope_device__site", relationship_direction=RelationshipDirection.BIDIR),),
        values=(site_b.id,),
    )

    number = await site_scoped_pool.get_resource(
        db=db,
        branch=default_branch,
        attribute=attribute.schema,
        identifier=device_b1.id,
        attribute_id=attribute.id,
        division=division_b,
    )

    assert attribute.value == 1
    assert number == 1


async def test_two_writers_in_one_division_receive_two_numbers_under_one_lock(
    db: InfrahubDatabase,
    default_branch: Branch,
    site_scoped_pool: CoreNumberPool,
    recording_lock_timeline: LockTimeline,
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    payloads = [device_payload(name=name, site=site_a, pool=site_scoped_pool) for name in ("device-a1", "device-a2")]
    lock_name = f"resource_pool.{site_scoped_pool.id}.{site_a.id}"
    start = recording_lock_timeline.checkpoint("writes")

    devices = await asyncio.gather(
        *(create_device_in_own_session(db=db, branch=default_branch, payload=payload) for payload in payloads)
    )

    assert sorted(vlan_id(device) for device in devices) == [1, 2]
    assert pool_lock_events(timeline=recording_lock_timeline, pool=site_scoped_pool, after=start) == [
        (lock_name, LockAction.ACQUIRE),
        (lock_name, LockAction.RELEASE),
        (lock_name, LockAction.ACQUIRE),
        (lock_name, LockAction.RELEASE),
    ]


async def test_two_writers_in_two_divisions_take_different_locks(
    db: InfrahubDatabase,
    default_branch: Branch,
    site_scoped_pool: CoreNumberPool,
    recording_lock_timeline: LockTimeline,
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    payloads = [
        device_payload(name="device-a1", site=site_a, pool=site_scoped_pool),
        device_payload(name="device-b1", site=site_b, pool=site_scoped_pool),
    ]
    lock_name_a = f"resource_pool.{site_scoped_pool.id}.{site_a.id}"
    lock_name_b = f"resource_pool.{site_scoped_pool.id}.{site_b.id}"

    start = recording_lock_timeline.checkpoint("writes")

    devices = await asyncio.gather(
        *(create_device_in_own_session(db=db, branch=default_branch, payload=payload) for payload in payloads)
    )

    assert [vlan_id(device) for device in devices] == [1, 1]
    acquired = [
        name
        for name, action in pool_lock_events(timeline=recording_lock_timeline, pool=site_scoped_pool, after=start)
        if action is LockAction.ACQUIRE
    ]
    assert sorted(acquired) == sorted([lock_name_a, lock_name_b])


async def test_a_full_division_is_refused_while_another_division_allocates(
    db: InfrahubDatabase, default_branch: Branch, scoped_schema: None
) -> None:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name="vlan-two-per-site",
        node=SCOPED_DEVICE.kind,
        node_attribute=SCOPED_ATTRIBUTE_NAME,
        start_range=1,
        end_range=2,
        allocation_scope=stored_scope(names=["site"]),
    )
    await pool.save(db=db)
    await add_pool_range(db=db, pool=pool, start=1, end=2)
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    await scoped_device(db=db, branch=default_branch, pool=pool, name="device-a1", site=site_a)
    await scoped_device(db=db, branch=default_branch, pool=pool, name="device-a2", site=site_a)

    with pytest.raises(
        ValidationError,
        match=rf"^Pool vlan-two-per-site \({pool.id}\) has no free number left in its ranges\. at vlan_id\.from_pool$",
    ):
        await scoped_device(db=db, branch=default_branch, pool=pool, name="device-a3", site=site_a)
    device_b1 = await scoped_device(db=db, branch=default_branch, pool=pool, name="device-b1", site=site_b)

    assert vlan_id(device_b1) == 1
    assert (
        await NodeManager.query(
            db=db, schema=SCOPED_DEVICE.kind, branch=default_branch, filters={"name__value": "device-a3"}
        )
        == []
    )


async def test_an_attribute_element_after_the_pooled_attribute_is_read_before_allocation(
    db: InfrahubDatabase, default_branch: Branch, site_role_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")

    leaf = await scoped_device(
        db=db, branch=default_branch, pool=site_role_scoped_pool, name="device-a1", site=site_a, role="leaf"
    )
    spine = await scoped_device(
        db=db, branch=default_branch, pool=site_role_scoped_pool, name="device-a2", site=site_a, role="spine"
    )
    second_leaf = await scoped_device(
        db=db, branch=default_branch, pool=site_role_scoped_pool, name="device-a3", site=site_a, role="leaf"
    )

    assert (vlan_id(leaf), vlan_id(spine), vlan_id(second_leaf)) == (1, 1, 2)


async def test_a_role_set_by_an_object_template_divides_the_lock_and_the_allocation(
    db: InfrahubDatabase, default_branch: Branch, templated_scoped_schema: None, recording_lock_timeline: LockTimeline
) -> None:
    pool = await scoped_pool(db=db, name="vlan-per-site-and-role", allocation_scope=["site", "role"])
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    await scoped_device_holding(
        db=db, branch=default_branch, pool=pool, name="device-a1", site=site_a, number=1, role="from-template"
    )
    template = await Node.init(db=db, schema=f"Template{SCOPED_DEVICE.kind}", branch=default_branch)
    await template.new(db=db, template_name="device-template", role="from-template", tags=["red"])
    await template.save(db=db)
    payload = device_payload(name="device-a2", site=site_a, pool=pool, role=None)
    payload["object_template"] = {"id": template.id}
    expected_lock_name = f"resource_pool.{pool.id}.{site_a.id}.from-template"
    start = recording_lock_timeline.checkpoint("write")

    device = await create_node(
        data=deepcopy(payload),
        db=db,
        branch=default_branch,
        schema=db.schema.get(name=SCOPED_DEVICE.kind, branch=default_branch, duplicate=False),
    )

    assert device.get_attribute("role").value == "from-template"
    assert vlan_id(device) == 2
    assert pool_lock_events(timeline=recording_lock_timeline, pool=pool, after=start) == [
        (expected_lock_name, LockAction.ACQUIRE),
        (expected_lock_name, LockAction.RELEASE),
    ]


async def test_a_role_set_by_a_profile_divides_the_lock_and_the_allocation(
    db: InfrahubDatabase,
    default_branch: Branch,
    site_role_scoped_pool: CoreNumberPool,
    recording_lock_timeline: LockTimeline,
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    await scoped_device_holding(
        db=db,
        branch=default_branch,
        pool=site_role_scoped_pool,
        name="device-a1",
        site=site_a,
        number=1,
        role="from-profile",
    )
    profile = await Node.init(db=db, schema=f"Profile{SCOPED_DEVICE.kind}", branch=default_branch)
    await profile.new(db=db, profile_name="device-profile", profile_priority=1000, role="from-profile")
    await profile.save(db=db)
    payload = device_payload(name="device-a2", site=site_a, pool=site_role_scoped_pool, role=None)
    payload["profiles"] = [{"id": profile.id}]
    expected_lock_name = f"resource_pool.{site_role_scoped_pool.id}.{site_a.id}.from-profile"
    start = recording_lock_timeline.checkpoint("write")

    device = await create_node(
        data=deepcopy(payload),
        db=db,
        branch=default_branch,
        schema=db.schema.get(name=SCOPED_DEVICE.kind, branch=default_branch, duplicate=False),
    )

    stored = await NodeManager.get_one(db=db, branch=default_branch, id=device.id, raise_on_error=True)
    assert stored.get_attribute("role").value == "from-profile"
    assert vlan_id(stored) == 2
    assert pool_lock_events(timeline=recording_lock_timeline, pool=site_role_scoped_pool, after=start) == [
        (expected_lock_name, LockAction.ACQUIRE),
        (expected_lock_name, LockAction.RELEASE),
    ]


async def test_a_provided_number_is_skipped_by_the_next_allocation_in_its_division_only(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-a1", site=site_a, number=1
    )

    device_a2 = await scoped_device(db=db, branch=default_branch, pool=site_scoped_pool, name="device-a2", site=site_a)
    device_b1 = await scoped_device(db=db, branch=default_branch, pool=site_scoped_pool, name="device-b1", site=site_b)

    assert (vlan_id(device_a2), vlan_id(device_b1)) == (2, 1)


async def test_an_allocation_on_a_branch_whose_schema_lacks_a_scope_element_is_refused(
    db: InfrahubDatabase, default_branch: Branch, scoped_schema: None
) -> None:
    branch = await create_branch(branch_name="predates-the-zone", db=db)
    device_with_zone = deepcopy(SCOPED_DEVICE)
    device_with_zone.attributes.append(AttributeSchema(name="zone", kind="Text", optional=False))
    await load_schema(db=db, schema=SchemaRoot(nodes=[device_with_zone]), update_db=True)
    pool = await scoped_pool(db=db, name="vlan-per-zone", allocation_scope=["zone"])
    site = await scoped_site(db=db, branch=branch, name="site-a")

    with pytest.raises(
        ValidationError,
        match=re.escape(
            'the scope element "zone" of pool vlan-per-zone does not exist on ScopeDevice on branch'
            " predates-the-zone; rebase the branch to get it at vlan_id.from_pool"
        ),
    ):
        await scoped_device(db=db, branch=branch, pool=pool, name="device-1", site=site)

    assert await NodeManager.query(db=db, schema=SCOPED_DEVICE.kind, branch=branch) == []


async def test_an_unscoped_pool_keeps_allocating_from_one_space(
    db: InfrahubDatabase,
    default_branch: Branch,
    unscoped_device_pool: CoreNumberPool,
    recording_lock_timeline: LockTimeline,
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    lock_name = f"resource_pool.{unscoped_device_pool.id}"
    start = recording_lock_timeline.checkpoint("writes")

    devices = [
        await create_device_in_own_session(
            db=db, branch=default_branch, payload=device_payload(name=name, site=site, pool=unscoped_device_pool)
        )
        for name, site in (("device-a1", site_a), ("device-b1", site_b), ("device-a2", site_a))
    ]

    assert [vlan_id(device) for device in devices] == [1, 2, 3]
    assert pool_lock_events(timeline=recording_lock_timeline, pool=unscoped_device_pool, after=start) == 3 * [
        (lock_name, LockAction.ACQUIRE),
        (lock_name, LockAction.RELEASE),
    ]


@pytest.mark.parametrize("allocation_scope", [["site"], None], ids=["scoped", "unscoped"])
async def test_a_site_named_by_an_unknown_name_is_refused_as_without_a_scope(
    db: InfrahubDatabase,
    default_branch: Branch,
    site_default_filter_schema: None,
    allocation_scope: list[str] | None,
) -> None:
    pool = await scoped_pool(db=db, name="vlan", allocation_scope=allocation_scope)
    payload = device_payload(name="device-1", site=await scoped_site(db=db, branch=default_branch, name="a"), pool=pool)
    payload["site"] = {"id": "unknown-site"}

    with pytest.raises(NodeNotFoundError) as exc_info:
        await create_node(
            data=payload,
            db=db,
            branch=default_branch,
            schema=db.schema.get(name=SCOPED_DEVICE.kind, branch=default_branch, duplicate=False),
        )

    assert exc_info.value.node_type == "ScopeSite"
    assert exc_info.value.identifier == "unknown-site"
    assert exc_info.value.message == "Unable to find the node unknown-site / ScopeSite in the database."
    assert await NodeManager.query(db=db, schema=SCOPED_DEVICE.kind, branch=default_branch) == []


async def test_a_site_named_by_its_hfid_allocates_in_its_division(
    db: InfrahubDatabase,
    default_branch: Branch,
    site_scoped_pool: CoreNumberPool,
    recording_lock_timeline: LockTimeline,
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    await scoped_device(db=db, branch=default_branch, pool=site_scoped_pool, name="device-a1", site=site_a)
    payload = device_payload(name="device-b1", site=site_b, pool=site_scoped_pool)
    payload["site"] = {"hfid": ["site-b"]}
    expected_lock_name = f"resource_pool.{site_scoped_pool.id}.{site_b.id}"
    start = recording_lock_timeline.checkpoint("write")

    device = await create_device_in_own_session(db=db, branch=default_branch, payload=payload)

    assert vlan_id(device) == 1
    assert pool_lock_events(timeline=recording_lock_timeline, pool=site_scoped_pool, after=start) == [
        (expected_lock_name, LockAction.ACQUIRE),
        (expected_lock_name, LockAction.RELEASE),
    ]
