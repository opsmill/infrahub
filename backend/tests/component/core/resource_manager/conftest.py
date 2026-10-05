from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.constants import BranchSupportType, InfrahubKind
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from tests.helpers.agnostic_edges import TEST_ACTOR_ID, IsReservedEdge, is_reserved_edge_on
from tests.helpers.schema.agnostic_retirement import AGNOSTIC_RETIREMENT_SCHEMA, WIDGET_KIND

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import SchemaRoot
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

SERIAL_POOL_START = 7001
SERIAL_POOL_END = 7010
SERIAL_ATTRIBUTE_NAME = "serial"


@pytest.fixture
async def agnostic_schema(db: InfrahubDatabase, default_branch: Branch) -> SchemaBranch:
    """The widget kind with its pooled `serial` attribute branch-agnostic."""
    return registry.schema.register_schema(schema=AGNOSTIC_RETIREMENT_SCHEMA, branch=default_branch.name)


@pytest.fixture
async def serial_pool(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> CoreNumberPool:
    """Bound to the kind and attribute by name, so it fits whichever branch support the test registers."""
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name="serial-pool",
        node=WIDGET_KIND,
        node_attribute=SERIAL_ATTRIBUTE_NAME,
        start_range=SERIAL_POOL_START,
        end_range=SERIAL_POOL_END,
    )
    await pool.save(db=db)
    return pool


async def pooled_holder(db: InfrahubDatabase, branch: Branch, kind: str, pool: CoreNumberPool, name: str) -> Node:
    """An object of the kind holding a `serial` the pool allocated, with the pool's IS_RESERVED edge open on it."""
    holder = await Node.init(db=db, schema=kind, branch=branch)
    await holder.new(db=db, name=name, serial={"from_pool": {"id": pool.id}})
    await holder.save(db=db)
    assert (
        await is_reserved_edge_on(db=db, pool_id=pool.id, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME)
        == IsReservedEdge.OPEN
    )
    return holder


def widget_schema(serial_branch_support: BranchSupportType) -> SchemaRoot:
    """The widget schema with its pooled attribute given the requested branch support."""
    schema = deepcopy(AGNOSTIC_RETIREMENT_SCHEMA)
    widget = next(node for node in schema.nodes if node.kind == WIDGET_KIND)
    widget.get_attribute(name=SERIAL_ATTRIBUTE_NAME).branch = serial_branch_support
    return schema


async def pooled_widget(
    db: InfrahubDatabase, default_branch: Branch, pool: CoreNumberPool, support: BranchSupportType
) -> Node:
    """Register the widget with its pooled serial at the given branch support and allocate one."""
    registry.schema.register_schema(schema=widget_schema(serial_branch_support=support), branch=default_branch.name)
    return await pooled_holder(db=db, branch=default_branch, kind=WIDGET_KIND, pool=pool, name="holds-a-pooled-serial")


async def delete_branch(db: InfrahubDatabase, branch: Branch) -> None:
    result = await BranchDataDeleter(db=db, batch_size=5).delete(branch=branch, user_id=TEST_ACTOR_ID)
    assert result.branch_deleted
