from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import SYSTEM_USER_ID, InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from infrahub.exceptions import DivisionExhaustedError, PoolExhaustedError
from infrahub.pools.existing_node_numbers import build_existing_node_number_allocator
from tests.helpers.number_pool import (
    SCOPED_ATTRIBUTE_NAME,
    SCOPED_DEVICE,
    SCOPED_POOL_SCHEMA,
    save_schema_kinds,
    scoped_device_holding,
    scoped_pool,
    scoped_site,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


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


@pytest.fixture
async def unscoped_device_pool(db: InfrahubDatabase, scoped_schema: None) -> CoreNumberPool:
    return await scoped_pool(db=db, name="vlan-shared", allocation_scope=None)


async def unnumbered_device(db: InfrahubDatabase, branch: Branch, name: str, site: Node) -> Node:
    device = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=branch)
    await device.new(db=db, name=name, role="leaf", tags=["red"], site=site)
    await device.save(db=db)
    return device


async def allocate_existing(
    db: InfrahubDatabase, branch: Branch, pool: CoreNumberPool, devices: list[Node], kind: str = SCOPED_DEVICE.kind
) -> int:
    """Load the nodes from the database, then allocate their `vlan_id` in the given order."""
    allocator = build_existing_node_number_allocator(db=db, branch=branch)
    loaded = await NodeManager.get_many(db=db, branch=branch, ids=[device.id for device in devices])
    attribute = registry.schema.get(name=kind, branch=branch, duplicate=False).get_attribute(name=SCOPED_ATTRIBUTE_NAME)
    return await allocator.allocate(
        pool=pool,
        attribute=attribute,
        nodes=[loaded[device.id] for device in devices],
        branch=branch,
        at=Timestamp(),
        user_id=SYSTEM_USER_ID,
    )


async def stored_vlan_ids(db: InfrahubDatabase, branch: Branch, devices: list[Node]) -> dict[str, int | None]:
    loaded = await NodeManager.get_many(db=db, branch=branch, ids=[device.id for device in devices])
    return {
        str(node.get_attribute("name").value): node.get_attribute(SCOPED_ATTRIBUTE_NAME).value
        for node in loaded.values()
    }


async def test_scoped_pool_numbers_each_site_from_one(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    devices = [
        await unnumbered_device(db=db, branch=default_branch, name="device-a1", site=site_a),
        await unnumbered_device(db=db, branch=default_branch, name="device-b1", site=site_b),
        await unnumbered_device(db=db, branch=default_branch, name="device-a2", site=site_a),
    ]

    allocated = await allocate_existing(db=db, branch=default_branch, pool=site_scoped_pool, devices=devices)

    assert allocated == 3
    assert await stored_vlan_ids(db=db, branch=default_branch, devices=devices) == {
        "device-a1": 1,
        "device-b1": 1,
        "device-a2": 2,
    }
    await verify_graph(db=db)


async def test_unscoped_pool_numbers_nodes_in_the_given_order(
    db: InfrahubDatabase, default_branch: Branch, unscoped_device_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    devices = [
        await unnumbered_device(db=db, branch=default_branch, name="device-a1", site=site_a),
        await unnumbered_device(db=db, branch=default_branch, name="device-b1", site=site_b),
        await unnumbered_device(db=db, branch=default_branch, name="device-a2", site=site_a),
    ]

    allocated = await allocate_existing(db=db, branch=default_branch, pool=unscoped_device_pool, devices=devices)

    assert allocated == 3
    assert await stored_vlan_ids(db=db, branch=default_branch, devices=devices) == {
        "device-a1": 1,
        "device-b1": 2,
        "device-a2": 3,
    }
    await verify_graph(db=db)


async def test_node_with_a_reservation_in_its_site_keeps_the_reserved_number(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    devices = [
        await unnumbered_device(db=db, branch=default_branch, name="device-a1", site=site_a),
        await scoped_device_holding(
            db=db, branch=default_branch, pool=site_scoped_pool, name="device-a7", site=site_a, number=7
        ),
    ]

    allocated = await allocate_existing(db=db, branch=default_branch, pool=site_scoped_pool, devices=devices)

    assert allocated == 2
    assert await stored_vlan_ids(db=db, branch=default_branch, devices=devices) == {
        "device-a1": 1,
        "device-a7": 7,
    }
    await verify_graph(db=db)


async def test_scope_values_set_by_a_profile_place_the_node_in_the_division_they_give(
    db: InfrahubDatabase, default_branch: Branch, scoped_schema: None
) -> None:
    """The device that takes its site and role from a profile shares the division of a device that sets them."""
    pool = await scoped_pool(db=db, name="vlan-per-site-and-role", allocation_scope=["site", "role"])
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    profile = await Node.init(db=db, schema=f"Profile{SCOPED_DEVICE.kind}", branch=default_branch)
    await profile.new(db=db, profile_name="site-a-spine", profile_priority=1000, site=site_a, role="spine")
    await profile.save(db=db)
    leaf = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=default_branch)
    await leaf.new(db=db, name="device-a-leaf", role="leaf", tags=["red"], site=site_a)
    await leaf.save(db=db)
    from_profile = await create_node(
        data={"name": {"value": "device-a-spine-from-profile"}, "tags": {"value": ["red"]}, "profiles": [profile]},
        db=db,
        branch=default_branch,
        schema=db.schema.get(name=SCOPED_DEVICE.kind, branch=default_branch, duplicate=False),
    )
    spine = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=default_branch)
    await spine.new(db=db, name="device-a-spine", role="spine", tags=["red"], site=site_a)
    await spine.save(db=db)
    other_site_spine = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=default_branch)
    await other_site_spine.new(db=db, name="device-b-spine", role="spine", tags=["red"], site=site_b)
    await other_site_spine.save(db=db)
    devices = [leaf, from_profile, spine, other_site_spine]
    stored = await NodeManager.get_one(db=db, branch=default_branch, id=from_profile.id, raise_on_error=True)
    assert stored.get_attribute("role").is_from_profile is True
    assert (await stored.get_relationship("site").get_relationships(db=db))[0].is_from_profile is True

    allocated = await allocate_existing(db=db, branch=default_branch, pool=pool, devices=devices)

    assert allocated == 4
    assert await stored_vlan_ids(db=db, branch=default_branch, devices=devices) == {
        "device-a-leaf": 1,
        "device-a-spine-from-profile": 1,
        "device-a-spine": 2,
        "device-b-spine": 1,
    }
    await verify_graph(db=db)


def migration_exhaustion_pattern(pool: CoreNumberPool, description: str, count: int, kind: str, size: int) -> str:
    text = (
        f"Pool {pool.get_attribute('name').value} ({pool.id}) has no free number left in its ranges for {description}:"
        f" {count} node(s) of {kind} being filled are in this division and the ranges hold {size} number(s)."
    )
    return f"^{re.escape(text)}$"


async def test_full_site_names_the_site_its_node_count_and_the_range_size(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    devices = [await unnumbered_device(db=db, branch=default_branch, name="device-b1", site=site_b)]
    devices += [
        await unnumbered_device(db=db, branch=default_branch, name=f"device-a{index}", site=site_a)
        for index in range(1, 13)
    ]

    with pytest.raises(
        PoolExhaustedError,
        match=migration_exhaustion_pattern(
            pool=site_scoped_pool, description=f"site '{site_a.id}'", count=12, kind=SCOPED_DEVICE.kind, size=10
        ),
    ) as exc_info:
        await allocate_existing(db=db, branch=default_branch, pool=site_scoped_pool, devices=devices)

    assert isinstance(exc_info.value.__cause__, DivisionExhaustedError)


# Two scalar scope elements, so two divisions can hold different values that join into the same dotted key.
SCOPED_ROUTER = NodeSchema(
    name="Router",
    namespace="Scope",
    label="Router",
    human_friendly_id=["name__value"],
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name=SCOPED_ATTRIBUTE_NAME, kind="Number", optional=True),
        AttributeSchema(name="role", kind="Text", optional=False),
        AttributeSchema(name="row", kind="Text", optional=False),
    ],
)


@pytest.fixture
async def role_row_scoped_pool(db: InfrahubDatabase, scoped_schema: None) -> CoreNumberPool:
    await save_schema_kinds(db=db, schema=SchemaRoot(nodes=[SCOPED_ROUTER]))
    return await scoped_pool(db=db, name="vlan-per-role-row", allocation_scope=["role", "row"], kind=SCOPED_ROUTER.kind)


async def unnumbered_router(db: InfrahubDatabase, branch: Branch, name: str, role: str, row: str) -> Node:
    router = await Node.init(db=db, schema=SCOPED_ROUTER.kind, branch=branch)
    await router.new(db=db, name=name, role=role, row=row)
    await router.save(db=db)
    return router


async def test_divisions_sharing_a_key_are_counted_apart(
    db: InfrahubDatabase, default_branch: Branch, role_row_scoped_pool: CoreNumberPool
) -> None:
    """Both divisions join into the key `leaf.a.b`, but only the routers of the full one are counted."""
    routers = [
        await unnumbered_router(db=db, branch=default_branch, name=f"router-other-{index}", role="leaf", row="a.b")
        for index in range(1, 4)
    ]
    routers += [
        await unnumbered_router(db=db, branch=default_branch, name=f"router-full-{index}", role="leaf.a", row="b")
        for index in range(1, 12)
    ]

    with pytest.raises(
        PoolExhaustedError,
        match=migration_exhaustion_pattern(
            pool=role_row_scoped_pool,
            description="role 'leaf.a', row 'b'",
            count=11,
            kind=SCOPED_ROUTER.kind,
            size=10,
        ),
    ):
        await allocate_existing(
            db=db, branch=default_branch, pool=role_row_scoped_pool, devices=routers, kind=SCOPED_ROUTER.kind
        )
