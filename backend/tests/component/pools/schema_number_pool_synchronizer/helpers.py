"""Schemas and runs shared by the schema number pool synchronizer tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer, SchemaNumberPoolSyncResult
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from infrahub.pools.scoped_number_pool_reader import ScopedNumberPoolReader
from tests.helpers.number_pool import register_and_provision_number_pools

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.attribute_parameters import NumberPoolParameters
    from infrahub.database import InfrahubDatabase


COUNTER_KIND = "TestingCounter"


def counter_schema(parameters: NumberPoolParameters) -> SchemaRoot:
    return SchemaRoot(
        nodes=[
            NodeSchema(
                name="Counter",
                namespace="Testing",
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(
                        name="counter",
                        kind="NumberPool",
                        optional=False,
                        read_only=True,
                        unique=True,
                        parameters=parameters,
                    ),
                ],
            )
        ]
    )


async def run_synchronizer(db: InfrahubDatabase) -> SchemaNumberPoolSyncResult:
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    return await SchemaNumberPoolSynchronizer(
        db=db,
        scope_reader=ScopedNumberPoolReader(db=db),
        schema_manager=registry.schema,
        upserter=upserter,
        range_store_factory=NumberPoolRepository,
    ).run()


async def provision_pool(db: InfrahubDatabase, branch: Branch, parameters: NumberPoolParameters) -> str:
    """Declare the counter attribute on the branch, let the synchronizer create its pool, and return the pool id."""
    await register_and_provision_number_pools(db=db, branch=branch, schema=counter_schema(parameters=parameters))
    pools = await NodeManager.query(
        db=db,
        schema=CoreNumberPool,
        filters={"node__value": COUNTER_KIND, "node_attribute__value": "counter"},
        branch_agnostic=True,
    )
    assert len(pools) == 1
    return pools[0].get_id()
