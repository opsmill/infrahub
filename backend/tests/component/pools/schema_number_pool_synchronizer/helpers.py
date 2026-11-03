"""Schemas and runs shared by the schema number pool synchronizer tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.pools.number_pool_locker import NumberPoolLock
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer, SchemaNumberPoolSyncResult
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from infrahub.pools.scope import AllocationScopeResolver
from infrahub.pools.scoped_number_pool_reader import ScopedNumberPoolReader
from tests.helpers.number_pool import SCOPED_DEVICE, register_and_provision_number_pools

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
        pool_locker=NumberPoolLock(db=db),
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


async def create_device_pool(db: InfrahubDatabase, name: str, scope: list[str]) -> str:
    """Create a user pool over the device's vlan_id with the scope resolved on the default branch, and return its id."""
    allocation_scope = AllocationScopeResolver(
        schema_branch=registry.schema.get_schema_branch(name=registry.default_branch)
    ).resolve(kind=SCOPED_DEVICE.kind, entries=scope)
    pool = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name=name,
        node=SCOPED_DEVICE.kind,
        node_attribute="vlan_id",
        start_range=1,
        end_range=10,
        allocation_scope=None if allocation_scope.is_empty else allocation_scope.to_stored(),
    )
    await pool.save(db=db)
    return pool.get_id()


async def stored_scope_of(db: InfrahubDatabase, pool_id: str) -> list[dict[str, str]] | None:
    pool = await NodeManager.get_one(db=db, id=pool_id, kind=CoreNumberPool, branch_agnostic=True)
    assert pool is not None
    return pool.allocation_scope.value


def default_device() -> NodeSchema:
    device = registry.schema.get_schema_branch(name=registry.default_branch).get_node(name=SCOPED_DEVICE.kind)
    assert isinstance(device, NodeSchema)
    return device
