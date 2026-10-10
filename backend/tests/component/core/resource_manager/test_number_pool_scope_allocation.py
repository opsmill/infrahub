from __future__ import annotations

import re
from copy import deepcopy
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RelationshipDirection
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node.create import create_node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.pools.scope import Division, DivisionElementPath
from tests.helpers.number_pool import (
    SCOPED_ATTRIBUTE_NAME,
    SCOPED_DEVICE,
    SCOPED_POOL_SCHEMA,
    SCOPED_SITE,
    add_pool_range,
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
    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


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
