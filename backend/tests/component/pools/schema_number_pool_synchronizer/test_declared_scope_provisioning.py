"""The synchronizer provisions the other pools when a declared scope does not resolve on the default branch."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.attribute_schema import AttributeSchema
from tests.component.pools.schema_number_pool_synchronizer.helpers import COUNTER_KIND, counter_schema, run_synchronizer
from tests.helpers.number_pool import SCOPED_DEVICE, SCOPED_POOL_SCHEMA
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def test_declaration_the_default_branch_cannot_resolve_leaves_later_pools_created(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A declared scope the default branch no longer resolves creates no pool, and the other declarations get theirs."""
    await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
    scoped_branch = await create_branch(db=db, branch_name="scope-gone")
    device = copy.deepcopy(SCOPED_DEVICE)
    device.attributes.append(
        AttributeSchema(
            name="vlan_index",
            kind="NumberPool",
            optional=False,
            read_only=True,
            parameters=NumberPoolParameters(start_range=1, end_range=10, allocation_scope=["site"]),
        )
    )
    registry.schema.register_schema(schema=SchemaRoot(nodes=[device]), branch=scoped_branch.name)
    default_schema = registry.schema.get_schema_branch(name=registry.default_branch)
    default_device_without_site = default_schema.get_node(name=SCOPED_DEVICE.kind)
    default_device_without_site.relationships = [
        relationship for relationship in default_device_without_site.relationships if relationship.name != "site"
    ]
    default_schema.set(name=SCOPED_DEVICE.kind, schema=default_device_without_site)
    counter_branch = await create_branch(db=db, branch_name="counter-pool")
    registry.schema.register_schema(
        schema=counter_schema(parameters=NumberPoolParameters(start_range=1, end_range=100)), branch=counter_branch.name
    )

    result = await run_synchronizer(db=db)

    device_pools = await NodeManager.query(
        db=db, schema=CoreNumberPool, filters={"node__value": SCOPED_DEVICE.kind}, branch_agnostic=True
    )
    counter_pools = await NodeManager.query(
        db=db, schema=CoreNumberPool, filters={"node__value": COUNTER_KIND}, branch_agnostic=True
    )
    assert (len(device_pools), len(counter_pools)) == (0, 1)
    assert result.refused_pools == [
        'ScopeDevice.vlan_index on scope-gone: "site" is not an attribute or a relationship of ScopeDevice on branch'
        " main at allocation_scope"
    ]


async def test_saving_a_branch_schema_holding_a_declaration_the_default_branch_cannot_resolve(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The branch schema saved for another pool, and reloaded later, keeps a declaration the default branch lost."""
    await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
    scoped_branch = await create_branch(db=db, branch_name="scope-gone")
    device = copy.deepcopy(SCOPED_DEVICE)
    device.attributes.extend(
        [
            AttributeSchema(
                name="vlan_index",
                kind="NumberPool",
                optional=False,
                read_only=True,
                parameters=NumberPoolParameters(start_range=1, end_range=10, allocation_scope=["site"]),
            ),
            AttributeSchema(
                name="vlan_serial",
                kind="NumberPool",
                optional=False,
                read_only=True,
                parameters=NumberPoolParameters(start_range=1, end_range=10),
            ),
        ]
    )
    registry.schema.register_schema(schema=SchemaRoot(nodes=[device]), branch=scoped_branch.name)
    default_schema = registry.schema.get_schema_branch(name=registry.default_branch)
    default_device_without_site = default_schema.get_node(name=SCOPED_DEVICE.kind)
    default_device_without_site.relationships = [
        relationship for relationship in default_device_without_site.relationships if relationship.name != "site"
    ]
    default_schema.set(name=SCOPED_DEVICE.kind, schema=default_device_without_site)
    counter_branch = await create_branch(db=db, branch_name="counter-pool")
    registry.schema.register_schema(
        schema=counter_schema(parameters=NumberPoolParameters(start_range=1, end_range=100)), branch=counter_branch.name
    )

    await run_synchronizer(db=db)
    reloaded = await registry.schema.load_schema_from_db(db=db, branch=scoped_branch)

    device_pools = await NodeManager.query(
        db=db, schema=CoreNumberPool, filters={"node__value": SCOPED_DEVICE.kind}, branch_agnostic=True
    )
    counter_pools = await NodeManager.query(
        db=db, schema=CoreNumberPool, filters={"node__value": COUNTER_KIND}, branch_agnostic=True
    )
    assert sorted(pool.node_attribute.value for pool in device_pools) == ["vlan_serial"]
    assert len(counter_pools) == 1
    reloaded_index = reloaded.get_node(name=SCOPED_DEVICE.kind).get_attribute(name="vlan_index")
    assert isinstance(reloaded_index.parameters, NumberPoolParameters)
    assert (reloaded_index.parameters.allocation_scope, reloaded_index.parameters.number_pool_id) == (["site"], None)
