from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.helpers.schema_builders import computed_jinja2_attr

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_create_with_jinja2_format_filter_on_number_pool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> None:
    """A Jinja2 macro that formats a pool-sourced attribute renders once the pool is allocated."""
    schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Sequence",
                namespace="Testing",
                attributes=[
                    AttributeSchema(name="title", kind="Text", optional=False),
                    AttributeSchema(
                        name="sequence_number",
                        kind="NumberPool",
                        optional=False,
                        read_only=True,
                        unique=True,
                        parameters=NumberPoolParameters(start_range=1, end_range=1000),
                    ),
                    computed_jinja2_attr(
                        name="serial_number",
                        template="TKT{{ '%09d' | format(sequence_number__value) }}",
                        unique=False,
                    ),
                ],
            ),
        ],
    )
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
    synchronizer = SchemaNumberPoolSynchronizer(db=db, schema_manager=registry.schema, upserter=upserter)
    await synchronizer.run()

    sequence_schema = registry.schema.get_node_schema(name="TestingSequence", branch=default_branch)
    ticket = await create_node(
        data={"title": "The first issue"},
        db=db,
        branch=default_branch,
        schema=sequence_schema,
    )

    assert ticket.sequence_number.value == 1
    assert ticket.serial_number.value == "TKT000000001"


async def test_new_with_unallocated_pool_renders_independent_macros(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> None:
    """With pools unallocated, a pool-dependent macro is skipped while other macros still render."""
    schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Sequence",
                namespace="Testing",
                attributes=[
                    AttributeSchema(name="title", kind="Text", optional=False),
                    AttributeSchema(
                        name="sequence_number",
                        kind="NumberPool",
                        optional=False,
                        read_only=True,
                        unique=True,
                        parameters=NumberPoolParameters(start_range=1, end_range=1000),
                    ),
                    computed_jinja2_attr(
                        name="serial_number",
                        template="TKT{{ '%09d' | format(sequence_number__value) }}",
                        unique=False,
                    ),
                    computed_jinja2_attr(
                        name="slug",
                        template="{{ title__value | lower }}",
                        unique=False,
                    ),
                ],
            ),
        ],
    )
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
    synchronizer = SchemaNumberPoolSynchronizer(db=db, schema_manager=registry.schema, upserter=upserter)
    await synchronizer.run()

    sequence_schema = registry.schema.get_node_schema(name="TestingSequence", branch=default_branch)
    node = await Node.init(db=db, schema=sequence_schema, branch=default_branch)
    await node.new(db=db, process_pools=False, title="First Issue")

    assert node.sequence_number.value is None
    assert node.slug.value == "first issue"
