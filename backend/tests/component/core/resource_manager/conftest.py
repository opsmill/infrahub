from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.constants import BranchSupportType, InfrahubKind
from infrahub.core.initialization import initialize_registry
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.pools.scope import AllocationScopeResolver
from tests.helpers.agnostic_edges import TEST_ACTOR_ID, IsReservedEdge, is_reserved_edge_on
from tests.helpers.number_pool import SCOPED_DEVICE, SCOPED_POOL_SCHEMA, SCOPED_SITE, add_pool_range
from tests.helpers.schema import TICKET, load_schema
from tests.helpers.schema.agnostic_retirement import AGNOSTIC_RETIREMENT_SCHEMA, WIDGET_KIND

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

SERIAL_POOL_START = 7001
SERIAL_POOL_END = 7010
SERIAL_ATTRIBUTE_NAME = "serial"

SCOPED_POOL_START = 1
SCOPED_POOL_END = 10
SCOPED_ATTRIBUTE_NAME = "vlan_id"


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
    await add_pool_range(db=db, pool=pool, start=SERIAL_POOL_START, end=SERIAL_POOL_END)
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


@pytest.fixture
async def ticket_schema(db: InfrahubDatabase, register_core_models_schema: SchemaBranch) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)


@pytest.fixture
async def scoped_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The scoped pool test schema, saved on the default branch so that its fields hold the ids a scope stores."""
    await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool


def stored_scope(names: list[str] | None) -> list[dict[str, str]] | None:
    """Return the stored form of a device scope naming the given fields, or None for an unscoped pool."""
    scope = AllocationScopeResolver(
        schema_branch=registry.schema.get_schema_branch(name=registry.default_branch)
    ).resolve(kind=SCOPED_DEVICE.kind, entries=names)
    return None if scope.is_empty else scope.to_stored()


async def scoped_pool(db: InfrahubDatabase, name: str, allocation_scope: list[str] | None) -> CoreNumberPool:
    """A pool over the device's `vlan_id` with the scope naming the given fields, allocating from one range."""
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name=name,
        node=SCOPED_DEVICE.kind,
        node_attribute=SCOPED_ATTRIBUTE_NAME,
        start_range=SCOPED_POOL_START,
        end_range=SCOPED_POOL_END,
        allocation_scope=stored_scope(names=allocation_scope),
    )
    await pool.save(db=db)
    await add_pool_range(db=db, pool=pool, start=SCOPED_POOL_START, end=SCOPED_POOL_END)
    return pool


@pytest.fixture
async def site_scoped_pool(db: InfrahubDatabase, scoped_schema: None) -> CoreNumberPool:
    return await scoped_pool(db=db, name="vlan-per-site", allocation_scope=["site"])


@pytest.fixture
async def site_role_scoped_pool(db: InfrahubDatabase, scoped_schema: None) -> CoreNumberPool:
    return await scoped_pool(db=db, name="vlan-per-site-and-role", allocation_scope=["site", "role"])


@pytest.fixture
async def unscoped_device_pool(db: InfrahubDatabase, scoped_schema: None) -> CoreNumberPool:
    return await scoped_pool(db=db, name="vlan-shared", allocation_scope=None)


async def scoped_site(db: InfrahubDatabase, branch: Branch, name: str) -> Node:
    site = await Node.init(db=db, schema=SCOPED_SITE.kind, branch=branch)
    await site.new(db=db, name=name)
    await site.save(db=db)
    return site


async def scoped_device(
    db: InfrahubDatabase,
    branch: Branch,
    pool: CoreNumberPool,
    name: str,
    site: Node,
    role: str = "leaf",
    tags: list[str] | None = None,
) -> Node:
    """A device of the site holding a `vlan_id` the pool allocated, with the pool's IS_RESERVED edge open on it."""
    device = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=branch)
    await device.new(
        db=db,
        name=name,
        role=role,
        tags=tags if tags is not None else ["red"],
        site=site,
        vlan_id={"from_pool": {"id": pool.id}},
    )
    await device.save(db=db)
    assert (
        await is_reserved_edge_on(db=db, pool_id=pool.id, node_id=device.id, attribute_name=SCOPED_ATTRIBUTE_NAME)
        == IsReservedEdge.OPEN
    )
    return device
