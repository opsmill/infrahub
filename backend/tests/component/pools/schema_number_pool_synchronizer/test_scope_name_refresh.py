"""The synchronizer rewrites the stored name of a scope element after a rename on the default branch."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.pools.scope import AllocationScopeResolver
from tests.component.pools.schema_number_pool_synchronizer.helpers import COUNTER_KIND, provision_pool, run_synchronizer
from tests.helpers.number_pool import SCOPED_DEVICE, SCOPED_POOL_SCHEMA
from tests.helpers.schema import load_schema, save_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


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


async def create_pool_with_stored_scope(db: InfrahubDatabase, name: str, kind: str, stored_scope: Any) -> str:
    """Create a user pool over vlan_id holding `stored_scope` as written, and return its id."""
    pool = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name=name,
        node=kind,
        node_attribute="vlan_id",
        start_range=1,
        end_range=10,
        allocation_scope=stored_scope,
    )
    await pool.save(db=db)
    return pool.get_id()


async def stored_scope_of(db: InfrahubDatabase, pool_id: str) -> list[dict[str, str]] | None:
    pool = await NodeManager.get_one(db=db, id=pool_id, kind=CoreNumberPool, branch_agnostic=True)
    assert pool is not None
    return pool.allocation_scope.value


async def scope_writes_of(db: InfrahubDatabase, pool_id: str) -> int:
    """Return how many values the pool's allocation_scope attribute has held, one more after each write."""
    query = """
    MATCH (:Node {uuid: $pool_id})-[:HAS_ATTRIBUTE]->(:Attribute {name: "allocation_scope"})-[edge:HAS_VALUE]->()
    RETURN count(edge) AS writes
    """
    results = await db.execute_query(query=query, params={"pool_id": pool_id})
    return results[0]["writes"]


def default_device() -> NodeSchema:
    device = registry.schema.get_schema_branch(name=registry.default_branch).get_node(name=SCOPED_DEVICE.kind)
    assert isinstance(device, NodeSchema)
    return device


async def test_renaming_scope_elements_rewrites_their_stored_names(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A renamed relationship and a renamed attribute keep their ids and the stored names follow the new names."""
    await save_schema(db=db, schema=SCOPED_POOL_SCHEMA)
    scoped_pool_id = await create_device_pool(db=db, name="vlan-per-site-and-role", scope=["site", "role"])
    unscoped_pool_id = await create_device_pool(db=db, name="vlan", scope=[])
    device = default_device()
    site_id = device.get_relationship(name="site").id
    role_id = device.get_attribute(name="role").id
    unscoped_writes = await scope_writes_of(db=db, pool_id=unscoped_pool_id)

    device.get_relationship(name="site").name = "location"
    device.get_attribute(name="role").name = "function"
    await save_schema(db=db, schema=SchemaRoot(nodes=[device]))
    await run_synchronizer(db=db)

    assert await stored_scope_of(db=db, pool_id=scoped_pool_id) == [
        {"id": site_id, "name": "location"},
        {"id": role_id, "name": "function"},
    ]
    assert await stored_scope_of(db=db, pool_id=unscoped_pool_id) is None
    assert await scope_writes_of(db=db, pool_id=unscoped_pool_id) == unscoped_writes


async def test_current_scope_names_are_not_rewritten(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A pool whose stored names match the default branch keeps its stored scope without a new write."""
    await save_schema(db=db, schema=SCOPED_POOL_SCHEMA)
    pool_id = await create_device_pool(db=db, name="vlan-per-site", scope=["site"])
    before = await stored_scope_of(db=db, pool_id=pool_id)
    writes = await scope_writes_of(db=db, pool_id=pool_id)

    await run_synchronizer(db=db)

    assert await stored_scope_of(db=db, pool_id=pool_id) == before
    assert await scope_writes_of(db=db, pool_id=pool_id) == writes


async def test_renaming_on_another_branch_keeps_the_stored_names(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Only the default branch names the scope elements, so a rename on another branch leaves the stored names."""
    await save_schema(db=db, schema=SCOPED_POOL_SCHEMA)
    pool_id = await create_device_pool(db=db, name="vlan-per-site", scope=["site"])
    before = await stored_scope_of(db=db, pool_id=pool_id)
    other_branch = await create_branch(db=db, branch_name="scope-rename")
    device = registry.schema.get_schema_branch(name=other_branch.name).get_node(name=SCOPED_DEVICE.kind)
    device.get_relationship(name="site").name = "location"

    await save_schema(db=db, schema=SchemaRoot(nodes=[device]), branch_name=other_branch.name)
    await run_synchronizer(db=db)

    assert await stored_scope_of(db=db, pool_id=pool_id) == before


async def test_schema_created_pool_stale_scope_name_is_rewritten(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A pool the schema created gets the name the default branch gives the element its stored id refers to."""
    pool_id = await provision_pool(
        db=db, branch=default_branch, parameters=NumberPoolParameters(start_range=1, end_range=100)
    )
    counter = registry.schema.get_schema_branch(name=registry.default_branch).get_node(name=COUNTER_KIND)
    name_id = counter.get_attribute(name="name").id
    assert name_id
    pool = await NodeManager.get_one(db=db, id=pool_id, kind=CoreNumberPool, branch_agnostic=True)
    assert pool is not None
    pool.allocation_scope.value = [{"id": name_id, "name": "label"}]
    await pool.save(db=db)

    await run_synchronizer(db=db)

    assert await stored_scope_of(db=db, pool_id=pool_id) == [{"id": name_id, "name": "name"}]


async def test_a_pool_whose_kind_is_gone_keeps_its_scope_while_a_stale_name_is_rewritten(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A pool whose kind the default branch does not define keeps its scope as written while a rename is applied."""
    await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
    renamed_pool_id = await create_device_pool(db=db, name="vlan-per-site", scope=["site"])
    undefined_kind_pool_id = await create_pool_with_stored_scope(
        db=db, name="vlan-undefined-kind", kind="ScopeGone", stored_scope=[{"id": "gone-site-id", "name": "site"}]
    )
    writes_before = await scope_writes_of(db=db, pool_id=undefined_kind_pool_id)
    device = default_device()
    site_id = device.get_relationship(name="site").id
    device.get_relationship(name="site").name = "location"
    await load_schema(db=db, schema=SchemaRoot(nodes=[device]), update_db=True)

    await run_synchronizer(db=db)

    assert await stored_scope_of(db=db, pool_id=renamed_pool_id) == [{"id": site_id, "name": "location"}]
    assert await stored_scope_of(db=db, pool_id=undefined_kind_pool_id) == [{"id": "gone-site-id", "name": "site"}]
    assert await scope_writes_of(db=db, pool_id=undefined_kind_pool_id) == writes_before
