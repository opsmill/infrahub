from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest
from rich.console import Console

from infrahub import lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, InfrahubKind, NumberPoolType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot, internal_schema
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

CAR_ATTRIBUTE_NAMES = ("asset_tag", "name", "status")
INHERITED_CAR_ATTRIBUTE_NAMES = ("asset_tag", "status")


@pytest.fixture(autouse=True)
def local_lock_registry() -> None:
    """Force in-process locks so pool allocations never wait on the shared redis registry."""
    lock.initialize_lock(local_only=True)


def recording_console() -> Console:
    return Console(record=True, width=200)


def build_generic(name: str, attributes: list[AttributeSchema]) -> GenericSchema:
    return GenericSchema(name=name, namespace="Test", branch=BranchSupportType.AWARE, attributes=attributes)


def build_inheriting_kind(name: str, inherit_from: list[str]) -> NodeSchema:
    return NodeSchema(
        name=name,
        namespace="Test",
        branch=BranchSupportType.AWARE,
        inherit_from=inherit_from,
        attributes=[AttributeSchema(name="name", kind="Text", optional=False)],
    )


def build_asset_schema() -> SchemaRoot:
    generic = build_generic(
        name="Asset",
        attributes=[
            AttributeSchema(name="status", kind="Text", default_value="active", optional=True),
            AttributeSchema(name="asset_tag", kind="Text", optional=False),
        ],
    )
    return SchemaRoot(generics=[generic], nodes=[build_inheriting_kind(name="Car", inherit_from=["TestAsset"])])


async def load_asset_schema(db: InfrahubDatabase, default_branch: Branch) -> None:
    schema_branch = registry.schema.register_schema(schema=build_asset_schema(), branch=default_branch.name)
    await registry.schema.load_schema_to_db(
        schema=schema_branch,
        branch=default_branch,
        db=db,
        at=Timestamp().subtract(seconds=120),
        limit=["TestAsset", "TestCar"],
    )
    default_branch.update_schema_hash()


@pytest.fixture
async def asset_schema(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema: SchemaBranch
) -> None:
    await load_asset_schema(db=db, default_branch=default_branch)


@pytest.fixture(scope="class")
async def asset_schema_class(db: InfrahubDatabase, default_branch_scope_class: Branch) -> Branch:
    """Class-scoped equivalent of asset_schema; returns the default branch it seeded."""
    registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch_scope_class.name)
    await load_asset_schema(db=db, default_branch=default_branch_scope_class)
    return default_branch_scope_class


async def create_healthy_car(db: InfrahubDatabase, branch: Branch, name: str, created_at: Timestamp) -> Node:
    car = await Node.init(db=db, schema="TestCar", branch=branch)
    await car.new(db=db, name=name, asset_tag=f"tag-{name}")
    await car.save(db=db, at=created_at)
    return car


async def delete_attribute_rows(db: InfrahubDatabase, node_uuid: str, attribute_names: list[str]) -> None:
    """Remove a node's attribute vertices outright, leaving no trace the rows ever existed."""
    query = """
    MATCH (n:Node { uuid: $uuid })-[:HAS_ATTRIBUTE]->(a:Attribute)
    WHERE a.name IN $names
    DETACH DELETE a
    """
    await db.execute_query(query=query, params={"uuid": node_uuid, "names": attribute_names})


def drop_registry_schema() -> None:
    """Leave the registry the way the upgrade command hands it to a migration.

    Registry initialization populates the branches and node classes but never sets the
    schema manager, so a migration invoked from the command line has to build its own and
    recover the default branch's schema from the database. Tests that run a migration with
    a fixture-populated registry never reach that path, and a migration that silently
    audits nothing but the core kinds passes them all.

    Call this immediately before invoking a migration, once the fixtures have finished
    seeding. The migration repopulates the registry as part of its own setup.
    """
    registry._schema = None


async def create_damaged_car(db: InfrahubDatabase, branch: Branch, created_at: Timestamp) -> str:
    """Seed an active, regularly-created TestCar carrying no rows for any of its schema attributes.

    Internal attribute rows the write path creates (e.g. display_label) stay in place,
    matching the real damage shape more closely than a bare vertex.
    """
    car = await create_healthy_car(db=db, branch=branch, name=f"damaged-{uuid4().hex[:8]}", created_at=created_at)
    await delete_attribute_rows(db=db, node_uuid=car.get_id(), attribute_names=list(CAR_ATTRIBUTE_NAMES))
    return car.get_id()


async def create_damaged_node(
    db: InfrahubDatabase, branch: Branch, labels: str, kind: str, created_at: Timestamp
) -> str:
    """Seed a bare active node vertex carrying no attribute rows at all.

    Used where the regular write path cannot produce the starting state: profile and
    template instances, and pool-backed kinds whose creation would allocate a value.
    """
    node_uuid = str(uuid4())
    query = """
    MATCH (root:Root)
    CREATE (n:Node:%(labels)s { uuid: $uuid, kind: $kind, branch_support: "aware" })
    CREATE (n)-[:IS_PART_OF { branch: $branch, branch_level: $branch_level, from: $from_time, status: "active" }]->(root)
    """ % {"labels": labels}
    await db.execute_query(
        query=query,
        params={
            "uuid": node_uuid,
            "kind": kind,
            "branch": branch.name,
            "branch_level": branch.hierarchy_level,
            "from_time": created_at.to_string(),
        },
    )
    return node_uuid


async def tombstone_attribute(
    db: InfrahubDatabase, branch: Branch, node_uuid: str, attribute_name: str, deleted_at: Timestamp
) -> str:
    """Delete a node's attribute through the object layer; return the deleted attribute's uuid."""
    node = await NodeManager.get_one(db=db, branch=branch, id=node_uuid)
    assert node is not None
    attribute = node.get_attribute(name=attribute_name)
    attribute_uuid = attribute.id
    assert attribute_uuid is not None
    await attribute.delete(db=db, at=deleted_at)
    return attribute_uuid


async def get_active_attribute_edge_details(
    db: InfrahubDatabase, node_uuid: str, attribute_names: tuple[str, ...] | None = None
) -> dict[str, tuple[str, str]]:
    """Return {attribute name: (branch, from-time)} for every open active HAS_ATTRIBUTE edge of a node.

    ``attribute_names`` restricts the result, e.g. to keep internal attribute rows
    (display_label, ...) out of exact-dict assertions. Limitation: an attribute deleted
    on a branch still shows its default-branch row here; per-branch latest-edge
    resolution is out of this helper's scope.
    """
    query = """
    MATCH (n:Node { uuid: $uuid })-[r:HAS_ATTRIBUTE { status: "active" }]->(a:Attribute)
    WHERE r.to IS NULL
    RETURN a.name AS name, r.branch AS branch, r.from AS from_time
    """
    results = await db.execute_query(query=query, params={"uuid": node_uuid})
    details: dict[str, tuple[str, str]] = {}
    for result in results:
        assert result["name"] not in details, f"duplicate active row for attribute {result['name']}"
        details[result["name"]] = (result["branch"], result["from_time"])
    if attribute_names is None:
        return details
    return {name: edge for name, edge in details.items() if name in attribute_names}


async def count_branch_level_attribute_edges(db: InfrahubDatabase, branch_name: str) -> int:
    """Count every attribute-row edge carried by the given branch."""
    query = """
    MATCH ()-[r:HAS_ATTRIBUTE|HAS_VALUE|IS_PROTECTED|IS_VISIBLE { branch: $branch_name }]->()
    RETURN count(r) AS edge_count
    """
    results = await db.execute_query(query=query, params={"branch_name": branch_name})
    return results[0]["edge_count"]


async def simulate_rebase(db: InfrahubDatabase, branch: Branch) -> None:
    """Move the branch point to now — the visibility effect a rebase has.

    A real rebase also rewrites the timestamps of the branch's own edges; tests that
    assert post-rebase edge times need the real rebase machinery instead.
    """
    branch.branched_from = Timestamp().to_string()
    await branch.save(db=db)
    registry.branch[branch.name] = branch


async def create_schema_number_pool(
    db: InfrahubDatabase, node: str, node_attribute: str, start_range: int = 1, end_range: int = 100
) -> Node:
    """Create the CoreNumberPool a schema-defined NumberPool attribute allocates from."""
    pool_id = str(uuid4())
    pool = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        id=pool_id,
        name=f"{node}.{node_attribute} [{pool_id}]",
        node=node,
        node_attribute=node_attribute,
        start_range=start_range,
        end_range=end_range,
        pool_type=NumberPoolType.SCHEMA.value,
    )
    await pool.save(db=db)
    return pool


def build_rack_unit_attribute(number_pool_id: str | None = None) -> AttributeSchema:
    return AttributeSchema(
        name="rack_unit",
        kind="NumberPool",
        optional=False,
        read_only=True,
        branch=BranchSupportType.AWARE,
        parameters=NumberPoolParameters(start_range=1, end_range=100, number_pool_id=number_pool_id),
    )


def build_server_schema(number_pool_id: str | None = None) -> SchemaRoot:
    generic = build_generic(name="Asset", attributes=[build_rack_unit_attribute(number_pool_id=number_pool_id)])
    return SchemaRoot(generics=[generic], nodes=[build_inheriting_kind(name="Server", inherit_from=["TestAsset"])])


async def load_server_schema(
    db: InfrahubDatabase, default_branch: Branch, number_pool_id: str | None = None
) -> SchemaBranch:
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    schema_branch = registry.schema.register_schema(
        schema=build_server_schema(number_pool_id=number_pool_id), branch=default_branch.name
    )
    await registry.schema.load_schema_to_db(
        schema=schema_branch,
        branch=default_branch,
        db=db,
        at=Timestamp().subtract(seconds=120),
        limit=["TestAsset", "TestServer"],
    )
    default_branch.update_schema_hash()
    return schema_branch


async def get_schema_pools(db: InfrahubDatabase) -> list[Node]:
    return await NodeManager.query(
        db=db,
        schema=InfrahubKind.NUMBERPOOL,
        filters={"pool_type__value": NumberPoolType.SCHEMA.value},
        branch_agnostic=True,
    )


@dataclass(frozen=True)
class EdgeShape:
    """Placement and peer identity of one edge of an attribute row, timestamps excluded."""

    branch: str
    branch_level: int
    peer: tuple[Any, ...]


@dataclass(frozen=True)
class AttributeRowShape:
    """Structure of a node's active attribute row, allocated value and timestamps excluded."""

    has_attribute_edge: tuple[str, int]
    property_keys: frozenset[str]
    branch_support: str
    edges: tuple[tuple[str, EdgeShape], ...]

    def edge(self, rel_type: str) -> EdgeShape:
        return dict(self.edges)[rel_type]

    @property
    def edge_types(self) -> set[str]:
        return {rel_type for rel_type, _ in self.edges}


async def get_pool_attribute_row_shape(
    db: InfrahubDatabase, node_uuid: str, attribute_name: str
) -> tuple[AttributeRowShape, int]:
    """Return the structure of a node's active attribute row and its allocated value.

    Only open active edges are considered.
    """
    query = """
    MATCH (n:Node { uuid: $uuid })-[ha:HAS_ATTRIBUTE { status: "active" }]->(a:Attribute { name: $attr_name })
    WHERE ha.to IS NULL
    MATCH (a)-[r { status: "active" }]->(peer)
    WHERE r.to IS NULL
    RETURN ha.branch AS ha_branch, ha.branch_level AS ha_branch_level,
        keys(a) AS attr_keys, a.branch_support AS branch_support,
        type(r) AS rel_type, r.branch AS r_branch, r.branch_level AS r_branch_level,
        labels(peer) AS peer_labels, peer.value AS peer_value,
        peer.is_default AS peer_is_default, peer.uuid AS peer_uuid
    """
    results = await db.execute_query(query=query, params={"uuid": node_uuid, "attr_name": attribute_name})
    assert results, f"no active attribute row found for {attribute_name} on node {node_uuid}"

    edges: dict[str, EdgeShape] = {}
    value: int | None = None
    for result in results:
        rel_type = result["rel_type"]
        assert rel_type not in edges, f"duplicate active {rel_type} edge on the attribute row"
        peer_labels = tuple(sorted(result["peer_labels"]))
        if rel_type == "HAS_VALUE":
            peer_descriptor: tuple[Any, ...] = (peer_labels, result["peer_is_default"])
            value = result["peer_value"]
        elif rel_type == "IS_PROTECTED":
            peer_descriptor = (peer_labels, result["peer_value"])
        elif rel_type == "HAS_SOURCE":
            peer_descriptor = (peer_labels, result["peer_uuid"])
        else:
            peer_descriptor = (peer_labels,)
        edges[rel_type] = EdgeShape(
            branch=result["r_branch"], branch_level=result["r_branch_level"], peer=peer_descriptor
        )

    assert isinstance(value, int)
    shape = AttributeRowShape(
        has_attribute_edge=(results[0]["ha_branch"], results[0]["ha_branch_level"]),
        property_keys=frozenset(results[0]["attr_keys"]),
        branch_support=results[0]["branch_support"],
        edges=tuple(sorted(edges.items())),
    )
    return shape, value


async def get_attribute_row_edge_placements(
    db: InfrahubDatabase, node_uuid: str, attribute_name: str
) -> set[tuple[str, str, int]]:
    """Return {(edge type, branch, branch_level)} for every edge of a node's active attribute row."""
    query = """
    MATCH (n:Node { uuid: $uuid })-[ha:HAS_ATTRIBUTE { status: "active" }]->(a:Attribute { name: $attr_name })
    WHERE ha.to IS NULL
    MATCH (a)-[r:HAS_ATTRIBUTE|HAS_VALUE|IS_PROTECTED { status: "active" }]-()
    WHERE r.to IS NULL
    RETURN DISTINCT type(r) AS rel_type, r.branch AS branch, r.branch_level AS branch_level
    """
    results = await db.execute_query(query=query, params={"uuid": node_uuid, "attr_name": attribute_name})
    return {(result["rel_type"], result["branch"], result["branch_level"]) for result in results}
