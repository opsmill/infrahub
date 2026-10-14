from __future__ import annotations

import asyncio
import re
from copy import deepcopy
from dataclasses import dataclass
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
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.pools.scope import Division, DivisionElementPath
from tests.adapters.lock.timeline import LockAction
from tests.helpers.agnostic_edges import IsReservedEdge, is_reserved_edge_on
from tests.helpers.number_pool import (
    SCOPED_ATTRIBUTE_NAME,
    SCOPED_CIRCUIT,
    SCOPED_DEVICE,
    SCOPED_POOL_END,
    SCOPED_POOL_SCHEMA,
    SCOPED_POOL_START,
    SCOPED_SITE,
    add_pool_range,
    pool_lock_events,
    provision_schema_number_pools,
    save_schema_kinds,
    scoped_device,
    scoped_device_holding,
    scoped_pool,
    scoped_site,
    stored_scope,
    vlan_id,
)

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


async def save_templated_scoped_schema(db: InfrahubDatabase) -> None:
    """Save the scoped pool test schema with an object template generated for the device."""
    schema = deepcopy(SCOPED_POOL_SCHEMA)
    next(node for node in schema.nodes if node.kind == SCOPED_DEVICE.kind).generate_template = True
    await save_schema_kinds(db=db, schema=schema)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool


@pytest.fixture
async def templated_scoped_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The scoped pool test schema with an object template generated for the device."""
    await save_templated_scoped_schema(db=db)


@pytest.fixture
async def site_default_filter_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The scoped pool test schema with a site that a write can name by its name as a default filter value."""
    schema = deepcopy(SCOPED_POOL_SCHEMA)
    next(node for node in schema.nodes if node.kind == SCOPED_SITE.kind).default_filter = "name__value"
    await save_schema_kinds(db=db, schema=schema)
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


@pytest.fixture
async def site_declared_pool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> CoreNumberPool:
    """The pool the schema creates for a device `vlan_id` that declares the scope `site`."""
    schema = deepcopy(SCOPED_POOL_SCHEMA)
    device = next(node for node in schema.nodes if node.kind == SCOPED_DEVICE.kind)
    device.attributes = [attribute for attribute in device.attributes if attribute.name != SCOPED_ATTRIBUTE_NAME]
    device.attributes.append(
        AttributeSchema(
            name=SCOPED_ATTRIBUTE_NAME,
            kind="NumberPool",
            optional=False,
            read_only=True,
            parameters=NumberPoolParameters(
                start_range=SCOPED_POOL_START, end_range=SCOPED_POOL_END, allocation_scope=["site"]
            ),
        )
    )
    await save_schema_kinds(db=db, schema=schema)
    await provision_schema_number_pools(db=db)
    pools = await NodeManager.query(
        db=db,
        schema=InfrahubKind.NUMBERPOOL,
        filters={"node__value": SCOPED_DEVICE.kind, "node_attribute__value": SCOPED_ATTRIBUTE_NAME},
    )
    assert len(pools) == 1
    pool = pools[0]
    assert isinstance(pool, CoreNumberPool)
    assert pool.get_attribute("allocation_scope").value == stored_scope(names=["site"])
    return pool


async def test_devices_of_two_sites_each_receive_the_first_number_of_a_pool_the_schema_declares(
    db: InfrahubDatabase, default_branch: Branch, site_declared_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")

    async def create_device(name: str, site: Node) -> Node:
        device = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=default_branch)
        await device.new(db=db, name=name, role="leaf", tags=["red"], site=site)
        await device.save(db=db)
        assert (
            await is_reserved_edge_on(
                db=db, pool_id=site_declared_pool.id, node_id=device.id, attribute_name=SCOPED_ATTRIBUTE_NAME
            )
            == IsReservedEdge.OPEN
        )
        return device

    device_a1 = await create_device(name="device-a1", site=site_a)
    device_b1 = await create_device(name="device-b1", site=site_b)
    device_a2 = await create_device(name="device-a2", site=site_a)

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


@dataclass(frozen=True)
class DirectionalScopeCase:
    name: str
    scope_field: str


DIRECTIONAL_SCOPE_CASES = [
    DirectionalScopeCase(name="outbound", scope_field="a_site"),
    DirectionalScopeCase(name="inbound", scope_field="z_site"),
]


@pytest.mark.parametrize("case", DIRECTIONAL_SCOPE_CASES, ids=[case.name for case in DIRECTIONAL_SCOPE_CASES])
async def test_a_directional_scope_element_divides_by_the_peer_on_its_side(
    db: InfrahubDatabase,
    default_branch: Branch,
    circuit_schema: None,
    recording_lock_timeline: LockTimeline,
    case: DirectionalScopeCase,
) -> None:
    """A circuit links to its other site through the same relationship identifier, in the opposite direction."""
    pool = await scoped_pool(
        db=db, name=f"vlan-per-{case.scope_field}", allocation_scope=[case.scope_field], kind=SCOPED_CIRCUIT.kind
    )
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    site_c = await scoped_site(db=db, branch=default_branch, name="site-c")

    async def create_circuit(name: str, scoped_end: Node, other_end: Node) -> tuple[int, list[str]]:
        a_site, z_site = (scoped_end, other_end) if case.scope_field == "a_site" else (other_end, scoped_end)
        start = recording_lock_timeline.checkpoint(name)
        circuit = await create_node(
            data={
                "name": {"value": name},
                "a_site": {"id": a_site.id},
                "z_site": {"id": z_site.id},
                "vlan_id": {"from_pool": {"id": pool.id}},
            },
            db=db,
            branch=default_branch,
            schema=db.schema.get(name=SCOPED_CIRCUIT.kind, branch=default_branch, duplicate=False),
        )
        acquired = [
            lock_name
            for lock_name, action in pool_lock_events(timeline=recording_lock_timeline, pool=pool, after=start)
            if action is LockAction.ACQUIRE
        ]
        return vlan_id(circuit), acquired

    first = await create_circuit(name="circuit-1", scoped_end=site_a, other_end=site_b)
    second = await create_circuit(name="circuit-2", scoped_end=site_b, other_end=site_a)
    third = await create_circuit(name="circuit-3", scoped_end=site_a, other_end=site_c)

    assert [first, second, third] == [
        (1, [f"resource_pool.{pool.id}.{site_a.id}"]),
        (1, [f"resource_pool.{pool.id}.{site_b.id}"]),
        (2, [f"resource_pool.{pool.id}.{site_a.id}"]),
    ]


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
    await save_schema_kinds(db=db, schema=SchemaRoot(nodes=[device_with_zone]))
    pool = await scoped_pool(db=db, name="vlan-per-zone", allocation_scope=["zone"])
    site = await scoped_site(db=db, branch=branch, name="site-a")

    with pytest.raises(
        ValidationError,
        match=re.escape(
            'the scope element "zone" of pool vlan-per-zone does not exist on ScopeDevice on branch'
            " predates-the-zone at vlan_id.from_pool"
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


@dataclass
class TemplatePoolDataset:
    """Three pools over the device's `vlan_id` that a device template each names, and the numbers they hold.

    The pool scoped by `site`: site-a holds 1. The unscoped pool: 1 is held. The pool scoped by `role`: the leaves
    hold 1 and the spines hold 1 to 3. Each template sets the role leaf.
    """

    default_branch: Branch
    pools: dict[str, CoreNumberPool]
    sites: dict[str, Node]
    templates: dict[str, Node]


@dataclass
class TemplatePoolCase:
    name: str
    pool: str
    site: str
    expected_number: int
    expected_division: str | None


TEMPLATE_POOL_CASES = [
    # The device sits in site-b, so the number site-a holds does not count.
    TemplatePoolCase(name="scoped-by-site", pool="site", site="site-b", expected_number=1, expected_division="site-b"),
    TemplatePoolCase(name="unscoped", pool="unscoped", site="site-b", expected_number=2, expected_division=None),
    # Only the template sets the role, and the spines hold 1 to 3, so 2 comes only from the leaf division.
    TemplatePoolCase(name="scoped-by-role", pool="role", site="site-a", expected_number=2, expected_division="leaf"),
]


class TestObjectTemplateNamingAPool:
    """Every test writes one device through a pool that no other test of the class writes through."""

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> TemplatePoolDataset:
        branch = default_branch_scope_class
        await save_templated_scoped_schema(db=db)
        pools = {
            "site": await scoped_pool(db=db, name="vlan-per-site", allocation_scope=["site"]),
            "unscoped": await scoped_pool(db=db, name="vlan", allocation_scope=None),
            "role": await scoped_pool(db=db, name="vlan-per-role", allocation_scope=["role"]),
        }
        sites = {name: await scoped_site(db=db, branch=branch, name=name) for name in ("site-a", "site-b")}
        for pool_name in ("site", "unscoped"):
            await scoped_device_holding(
                db=db,
                branch=branch,
                pool=pools[pool_name],
                name=f"{pool_name}-holder-1",
                site=sites["site-a"],
                number=1,
            )
        for role, numbers in (("leaf", [1]), ("spine", [1, 2, 3])):
            for number in numbers:
                await scoped_device_holding(
                    db=db,
                    branch=branch,
                    pool=pools["role"],
                    name=f"{role}-holder-{number}",
                    site=sites["site-a"],
                    number=number,
                    role=role,
                )
        templates = {}
        for pool_name, pool in pools.items():
            template = await Node.init(db=db, schema=f"Template{SCOPED_DEVICE.kind}", branch=branch)
            await template.new(
                db=db,
                template_name=f"template-of-{pool_name}",
                role="leaf",
                tags=["red"],
                vlan_id_from_resource_pool={"id": pool.id},
            )
            await template.save(db=db)
            templates[pool_name] = template
        return TemplatePoolDataset(default_branch=branch, pools=pools, sites=sites, templates=templates)

    @pytest.mark.parametrize("case", TEMPLATE_POOL_CASES, ids=[case.name for case in TEMPLATE_POOL_CASES])
    async def test_the_device_allocates_in_its_division_of_the_pool_its_template_names(
        self,
        db: InfrahubDatabase,
        dataset: TemplatePoolDataset,
        recording_lock_timeline: LockTimeline,
        case: TemplatePoolCase,
    ) -> None:
        branch = dataset.default_branch
        pool = dataset.pools[case.pool]
        payload = {
            "name": {"value": f"device-of-{case.name}"},
            "site": {"id": dataset.sites[case.site].id},
            "object_template": {"id": dataset.templates[case.pool].id},
        }
        division_key = (
            dataset.sites[case.expected_division].id
            if case.expected_division in dataset.sites
            else case.expected_division
        )
        expected_lock_name = f"resource_pool.{pool.id}" + (f".{division_key}" if division_key is not None else "")
        start = recording_lock_timeline.checkpoint("write")

        device = await create_device_in_own_session(db=db, branch=branch, payload=payload)

        stored = await NodeManager.get_one(db=db, branch=branch, id=device.id, raise_on_error=True)
        assert stored.get_attribute("role").value == "leaf"
        assert vlan_id(stored) == case.expected_number
        assert pool_lock_events(timeline=recording_lock_timeline, pool=pool, after=start) == [
            (expected_lock_name, LockAction.ACQUIRE),
            (expected_lock_name, LockAction.RELEASE),
        ]
