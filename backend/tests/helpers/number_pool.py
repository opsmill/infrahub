from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import ComputedAttributeKind, InfrahubKind
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_pool_shorthand import NumberPoolShorthandMirror
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.helpers.schema.snow import SNOW_INCIDENT, SNOW_TASK

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import AttributeSchema
    from infrahub.database import InfrahubDatabase


def snow_schema_with_format_identifier(
    identifier_template: str = "INC{{ '%09d' | format(number__value) }}",
    extra_incident_attrs: list[AttributeSchema] | None = None,
) -> SchemaRoot:
    """Snow schema whose incident identifier formats the pool value with a leading-zero filter."""
    task = copy.deepcopy(SNOW_TASK)
    task.get_attribute(name="number").parameters = NumberPoolParameters(start_range=1, end_range=1000)
    incident = copy.deepcopy(SNOW_INCIDENT)
    incident.get_attribute(name="identifier").computed_attribute = ComputedAttribute(
        kind=ComputedAttributeKind.JINJA2, jinja2_template=identifier_template
    )
    if extra_incident_attrs:
        incident.attributes.extend(extra_incident_attrs)
    return SchemaRoot(generics=[task], nodes=[incident])


async def register_and_provision_number_pools(db: InfrahubDatabase, branch: Branch, schema: SchemaRoot) -> None:
    """Register the schema and provision the number pools defined by its NumberPool attributes."""
    registry.schema.register_schema(schema=schema, branch=branch.name)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    synchronizer = SchemaNumberPoolSynchronizer(
        db=db, schema_manager=registry.schema, upserter=upserter, range_store_factory=NumberPoolRepository
    )
    await synchronizer.run()


def shorthand_mirror(db: InfrahubDatabase) -> NumberPoolShorthandMirror:
    return NumberPoolShorthandMirror(db=db, repository=NumberPoolRepository(db=db))


async def add_pool_range(db: InfrahubDatabase, pool: Node, start: int, end: int) -> Node:
    pool_range = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOLRANGE)
    await pool_range.new(db=db, start=start, end=end, pool=pool.get_id())
    await pool_range.save(db=db)
    return pool_range
