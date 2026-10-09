from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.protocols import CoreNumberPool as CoreNumberPoolProtocol
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.helpers.number_pool import (
    SCOPED_DEVICE,
    SCOPED_HOLDER,
    SCOPED_LINK,
    SCOPED_POD_HOLDER,
    SCOPED_POOL_SCHEMA,
    SCOPED_RACK,
    SCOPED_SITE,
)
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


def _pooled_attribute(name: str, scope: list[str]) -> AttributeSchema:
    return AttributeSchema(
        name=name,
        kind="NumberPool",
        optional=False,
        read_only=True,
        parameters=NumberPoolParameters(start_range=1, end_range=100, allocation_scope=scope),
    )


def _with_pooled_vlan_id[SchemaT: (NodeSchema, GenericSchema)](schema: SchemaT, scope: list[str]) -> SchemaT:
    pooled: SchemaT = copy.deepcopy(schema)
    pooled.attributes = [attribute for attribute in pooled.attributes if attribute.name != "vlan_id"]
    pooled.attributes.append(_pooled_attribute(name="vlan_id", scope=scope))
    return pooled


def _schema(device: NodeSchema = SCOPED_DEVICE, holder: GenericSchema = SCOPED_HOLDER) -> SchemaRoot:
    return SchemaRoot(generics=[holder], nodes=[SCOPED_SITE, SCOPED_RACK, SCOPED_LINK, device, SCOPED_POD_HOLDER])


async def _load_and_provision(db: InfrahubDatabase, schema: SchemaRoot, branch_name: str | None = None) -> None:
    """Save the schema on the branch, the default one when none is named, then let the synchronizer create the pools it declares."""
    await load_schema(db=db, schema=schema, branch_name=branch_name, update_db=True)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    await SchemaNumberPoolSynchronizer(
        db=db, schema_manager=registry.schema, upserter=upserter, range_store_factory=NumberPoolRepository
    ).run()


async def _schema_pool(db: InfrahubDatabase, kind: str, attribute: str) -> CoreNumberPoolProtocol:
    pools = await NodeManager.query(
        db=db,
        schema=CoreNumberPoolProtocol,
        filters={"node__value": kind, "node_attribute__value": attribute},
        branch_agnostic=True,
    )
    assert len(pools) == 1
    return pools[0]


def _saved_field_id(kind: str, name: str) -> str:
    field = registry.schema.get(name=kind, duplicate=False).get_field(name=name)
    assert field.id is not None
    return field.id


async def _site(db: InfrahubDatabase, branch: Branch, name: str) -> Node:
    site = await Node.init(db=db, schema=SCOPED_SITE.kind, branch=branch)
    await site.new(db=db, name=name)
    await site.save(db=db)
    return site


async def _device(db: InfrahubDatabase, branch: Branch, name: str, site: Node) -> Node:
    device = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=branch)
    await device.new(db=db, name=name, role="leaf", tags=["edge"], site=site)
    await device.save(db=db)
    return device


async def test_declared_scope_is_stored_as_ids_and_names(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await _load_and_provision(db=db, schema=_schema(device=_with_pooled_vlan_id(SCOPED_DEVICE, scope=["site", "role"])))

    pool = await _schema_pool(db=db, kind=SCOPED_DEVICE.kind, attribute="vlan_id")

    assert pool.allocation_scope.value == [
        {"id": _saved_field_id(kind=SCOPED_DEVICE.kind, name="site"), "name": "site"},
        {"id": _saved_field_id(kind=SCOPED_DEVICE.kind, name="role"), "name": "role"},
    ]


async def test_declared_scope_naming_a_field_the_same_load_adds_stores_its_saved_id(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
    device = copy.deepcopy(SCOPED_DEVICE)
    device.attributes.extend(
        [
            AttributeSchema(name="zone", kind="Text", optional=False),
            _pooled_attribute(name="zone_index", scope=["zone"]),
        ]
    )

    await _load_and_provision(db=db, schema=_schema(device=device))

    pool = await _schema_pool(db=db, kind=SCOPED_DEVICE.kind, attribute="zone_index")
    assert pool.allocation_scope.value == [
        {"id": _saved_field_id(kind=SCOPED_DEVICE.kind, name="zone"), "name": "zone"}
    ]


async def test_declared_scope_of_an_inherited_attribute_resolves_on_the_generic(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await _load_and_provision(db=db, schema=_schema(holder=_with_pooled_vlan_id(SCOPED_HOLDER, scope=["site"])))

    pool = await _schema_pool(db=db, kind=SCOPED_HOLDER.kind, attribute="vlan_id")

    assert pool.allocation_scope.value == [
        {"id": _saved_field_id(kind=SCOPED_HOLDER.kind, name="site"), "name": "site"}
    ]


async def test_declared_scope_on_another_branch_stores_the_default_branch_ids_and_names(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
    branch = await create_branch(db=db, branch_name="declared-scope")
    device = copy.deepcopy(SCOPED_DEVICE)
    device.attributes.append(_pooled_attribute(name="vlan_index", scope=["site"]))

    await _load_and_provision(db=db, schema=_schema(device=device), branch_name=branch.name)

    pool = await _schema_pool(db=db, kind=SCOPED_DEVICE.kind, attribute="vlan_index")
    assert pool.allocation_scope.value == [
        {"id": _saved_field_id(kind=SCOPED_DEVICE.kind, name="site"), "name": "site"}
    ]


async def test_declared_scope_on_a_branch_differing_from_the_existing_pool_is_not_attached(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
    branch = await create_branch(db=db, branch_name="other-scope")
    main_device = copy.deepcopy(SCOPED_DEVICE)
    main_device.attributes.append(_pooled_attribute(name="vlan_index", scope=["role"]))
    await _load_and_provision(db=db, schema=_schema(device=main_device))
    branch_device = copy.deepcopy(SCOPED_DEVICE)
    branch_device.attributes.append(_pooled_attribute(name="vlan_index", scope=["site"]))

    await _load_and_provision(db=db, schema=_schema(device=branch_device), branch_name=branch.name)

    pool = await _schema_pool(db=db, kind=SCOPED_DEVICE.kind, attribute="vlan_index")
    assert pool.allocation_scope.value == [
        {"id": _saved_field_id(kind=SCOPED_DEVICE.kind, name="role"), "name": "role"}
    ]
    branch_attribute = registry.schema.get(name=SCOPED_DEVICE.kind, branch=branch.name, duplicate=False).get_attribute(
        name="vlan_index"
    )
    assert isinstance(branch_attribute.parameters, NumberPoolParameters)
    assert branch_attribute.parameters.number_pool_id is None
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    with pytest.raises(
        ValidationError,
        match=rf"^ScopeDevice\.vlan_index: allocation_scope can't be changed after the pool is created; the pool"
        rf" ScopeDevice\.vlan_index \[{pool.id}\] is scoped by \['role'\]$",
    ):
        await upserter.upsert_number_pool(
            schema_node=registry.schema.get(name=SCOPED_DEVICE.kind, branch=branch.name, duplicate=False),
            attribute=branch_attribute,
            branch_name=branch.name,
        )


@pytest.mark.xfail(
    reason="per-division allocation lands with the allocation ticket", strict=True, raises=AssertionError
)
async def test_nodes_in_two_sites_each_receive_the_first_number(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await _load_and_provision(db=db, schema=_schema(device=_with_pooled_vlan_id(SCOPED_DEVICE, scope=["site"])))
    site_a = await _site(db=db, branch=default_branch, name="site-a")
    site_b = await _site(db=db, branch=default_branch, name="site-b")

    device_a = await _device(db=db, branch=default_branch, name="device-a", site=site_a)
    device_b = await _device(db=db, branch=default_branch, name="device-b", site=site_b)

    assert (device_a.get_attribute("vlan_id").value, device_b.get_attribute("vlan_id").value) == (1, 1)
