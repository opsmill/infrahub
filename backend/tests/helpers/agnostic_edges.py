"""Object builders, graph-shape readers, and shared assertions for the branch-agnostic tests.

The readers go to the edges directly rather than through the node manager: the subject of the
assertions is which edges carry a `to` timestamp and which do not, and a read through the manager
would hide the very states the tests exist to pin down. The builders that write raw Cypher do so
because the shape they produce is one no current code path can reach.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.node import Node
from tests.helpers.schema.agnostic_retirement import GADGET_KIND, WIDGET_KIND

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


async def create_widget(
    db: InfrahubDatabase, branch: Branch, name: str, serial: int, at: Timestamp | None = None, **kwargs: Any
) -> Node:
    """A widget carrying a branch-agnostic `serial` and an optional branch-agnostic `gadget` peer."""
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=branch)
    await widget.new(db=db, name=name, serial=serial, **kwargs)
    await widget.save(db=db, at=at)
    return widget


async def create_gadget(db: InfrahubDatabase, branch: Branch, name: str, at: Timestamp | None = None) -> Node:
    """The peer on the far side of a widget's branch-agnostic relationship."""
    gadget = await Node.init(db=db, schema=GADGET_KIND, branch=branch)
    await gadget.new(db=db, name=name)
    await gadget.save(db=db, at=at)
    return gadget


@dataclass(frozen=True)
class EdgeState:
    """One edge as these assertions care about it: what it is, where it sits, and whether it is open."""

    edge_type: str
    branch: str
    status: str
    from_time: str
    to_time: str | None
    to_user_id: str | None = None
    """Who closed the edge. `None` on an open edge, and on one closed before the actor was recorded."""

    @property
    def is_open(self) -> bool:
        return self.to_time is None

    @property
    def is_active(self) -> bool:
        return self.status == "active"


@dataclass(frozen=True)
class VertexMetadata:
    """The audit stamps a write leaves on a vertex, and the snapshot a rollback would restore from."""

    updated_at: str | None
    updated_by: str | None
    previous_updated_at: str | None
    previous_updated_by: str | None


def open_edges(edges: list[EdgeState]) -> list[EdgeState]:
    """Every open edge, one entry each.

    Counting distinct types instead undercounts a vertex holding two edges of one type, which is every
    relationship vertex, so an expected closure count is read from this and never from the types.
    """
    return [edge for edge in edges if edge.is_open]


def open_active_edges(edges: list[EdgeState]) -> list[EdgeState]:
    """The edges a retirement run is expected to close: open, and not already a tombstone."""
    return [edge for edge in edges if edge.is_open and edge.is_active]


def open_edge_types(edges: list[EdgeState]) -> set[str]:
    return {edge.edge_type for edge in open_edges(edges)}


def inverted_edges(edges: list[EdgeState]) -> list[EdgeState]:
    """The edges that end before they start, which a close stamped earlier than `from` would produce."""
    return [edge for edge in edges if edge.to_time is not None and edge.to_time < edge.from_time]


def edge_summary(edges: list[EdgeState]) -> list[tuple[str, str, str]]:
    """Order-independent view of a vertex's edges, for before/after comparison."""
    return sorted((edge.edge_type, edge.status, edge.to_time or "") for edge in edges)


def to_times(edges: list[EdgeState]) -> set[str | None]:
    """The distinct `to` stamps across a set of edges, for asserting a whole field closed at once."""
    return {edge.to_time for edge in edges}


def closing_actors(edges: list[EdgeState]) -> set[str | None]:
    """The distinct actors recorded on the closed edges, for asserting who a release is attributed to.

    Open edges are left out: they carry no actor, and including them would let a run that closed
    nothing satisfy an assertion about who closed what.
    """
    return {edge.to_user_id for edge in edges if not edge.is_open}


def expected_closed_at(edges: list[EdgeState], at: Timestamp) -> list[tuple[str, str, str]]:
    """What `edge_summary` should return once every open edge has been closed at `at`.

    Built edge by edge, never from the set of types: a vertex holds two edges of one type after a
    value update, and the superseded edge keeps the close stamp that update gave it.
    """
    return sorted((edge.edge_type, edge.status, edge.to_time or at.to_string()) for edge in edges)


def assert_attribute_retired_at(after: list[EdgeState], before: list[EdgeState], at: Timestamp) -> None:
    """The attribute's global edges were time-closed at `at`, never tombstoned."""
    assert edge_summary(after) == expected_closed_at(before, at)
    assert {edge.status for edge in after} == {"active"}, "retirement is a time-close, never a status tombstone"


def assert_relationship_retired_at(after: list[EdgeState], before: list[EdgeState], at: Timestamp) -> None:
    """No branch reads both peers live once the operation lands, so every open peer edge closes at `at`.

    Compared edge by edge against `before`: a peer update leaves a superseded relationship vertex
    behind, and that vertex's already-closed edges keep the stamp the update gave them.
    """
    assert edge_summary(after) == expected_closed_at(before, at)
    assert {edge.status for edge in after} == {"active"}, "retirement is a time-close, never a status tombstone"


async def attribute_global_edges(db: InfrahubDatabase, node_id: str, attribute_name: str) -> list[EdgeState]:
    """Every global-branch edge touching the attribute vertex, owning edge included."""
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
        WITH DISTINCT a
        MATCH (a)-[e]-()
        WHERE e.branch = $global_branch
        RETURN type(e) AS edge_type, e.branch AS branch, e.status AS status,
               e.from AS from_time, e.to AS to_time, e.to_user_id AS to_user_id
        """,
        params={"node_id": node_id, "attribute_name": attribute_name, "global_branch": GLOBAL_BRANCH_NAME},
    )
    return [EdgeState(**dict(result)) for result in results]


async def relationship_global_edges(db: InfrahubDatabase, node_id: str, identifier: str) -> list[EdgeState]:
    """Every global-branch edge of the relationship vertex reached from this node.

    Reached through the node rather than matched on the identifier alone, so a relationship built by
    another test sharing the database is not counted. The traversal is unfiltered on purpose: the edge
    it arrives over may itself have been closed by the run under assertion.
    """
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:IS_RELATED]-(r:Relationship {name: $identifier})
        WITH DISTINCT r
        MATCH (r)-[e]-()
        WHERE e.branch = $global_branch
        RETURN type(e) AS edge_type, e.branch AS branch, e.status AS status,
               e.from AS from_time, e.to AS to_time, e.to_user_id AS to_user_id
        """,
        params={"node_id": node_id, "identifier": identifier, "global_branch": GLOBAL_BRANCH_NAME},
    )
    return [EdgeState(**dict(result)) for result in results]


def attribute_vertex_uuid(node: Node, attribute_name: str) -> str:
    """The attribute vertex's own uuid, as the loaded node already knows it."""
    vertex_uuid = node.get_attribute(name=attribute_name).id
    assert vertex_uuid is not None, f"{node.get_kind()} has no saved {attribute_name} attribute"
    return vertex_uuid


def relationship_vertex_uuid(node: Node, relationship_name: str) -> str:
    """The relationship vertex's own uuid, as the loaded node already knows it."""
    relationship = node.get_relationship(name=relationship_name).get_one()
    assert relationship is not None, f"{node.get_kind()} holds no {relationship_name} peer"
    assert relationship.id is not None, f"{node.get_kind()} has an unsaved {relationship_name} peer"
    return str(relationship.id)


async def global_edges_by_vertex_uuid(db: InfrahubDatabase, vertex_uuid: str) -> list[EdgeState]:
    """Every global-branch edge of a field vertex matched by its own uuid."""
    results = await db.execute_query(
        query="""
        MATCH (v {uuid: $vertex_uuid})
        WHERE v:Attribute OR v:Relationship
        MATCH (v)-[e]-()
        WHERE e.branch = $global_branch
        RETURN type(e) AS edge_type, e.branch AS branch, e.status AS status,
               e.from AS from_time, e.to AS to_time, e.to_user_id AS to_user_id
        """,
        params={"vertex_uuid": vertex_uuid, "global_branch": GLOBAL_BRANCH_NAME},
    )
    return [EdgeState(**dict(result)) for result in results]


async def attribute_owning_edges(db: InfrahubDatabase, node_id: str, attribute_name: str) -> list[EdgeState]:
    """Every owning edge of the attribute vertex, on any branch."""
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
        WITH DISTINCT a
        MATCH (:Node)-[e:HAS_ATTRIBUTE]->(a)
        RETURN type(e) AS edge_type, e.branch AS branch, e.status AS status,
               e.from AS from_time, e.to AS to_time, e.to_user_id AS to_user_id
        """,
        params={"node_id": node_id, "attribute_name": attribute_name},
    )
    return [EdgeState(**dict(result)) for result in results]


async def existence_edges(db: InfrahubDatabase, node_id: str) -> list[EdgeState]:
    """Every existence edge of the node, on any branch."""
    results = await db.execute_query(
        query="""
        MATCH (n:Node {uuid: $node_id})-[e:IS_PART_OF]->(:Root)
        RETURN type(e) AS edge_type, e.branch AS branch, e.status AS status,
               e.from AS from_time, e.to AS to_time, e.to_user_id AS to_user_id
        """,
        params={"node_id": node_id},
    )
    return [EdgeState(**dict(result)) for result in results]


async def relationship_peer_shape(db: InfrahubDatabase, node_id: str, identifier: str) -> tuple[int, int]:
    """How many live global `IS_RELATED` edges this node's relationship has, and how many peers."""
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:IS_RELATED]-(r:Relationship {name: $identifier})
        WITH DISTINCT r
        MATCH (r)-[e:IS_RELATED]-(peer:Node)
        WHERE e.branch = $global_branch AND e.status = "active" AND e.to IS NULL
        RETURN count(e) AS edge_count, count(DISTINCT peer.uuid) AS peer_count
        """,
        params={"node_id": node_id, "identifier": identifier, "global_branch": GLOBAL_BRANCH_NAME},
    )
    return results[0]["edge_count"], results[0]["peer_count"]


async def node_vertex_count(db: InfrahubDatabase, node_id: str) -> int:
    """How many `:Node` vertices carry this uuid; more than one after a kind or inheritance change."""
    results = await db.execute_query(
        query="MATCH (n:Node {uuid: $node_id}) RETURN count(n) AS vertex_count",
        params={"node_id": node_id},
    )
    return results[0]["vertex_count"]


async def attribute_vertex_count(db: InfrahubDatabase, node_id: str, attribute_name: str) -> int:
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
        RETURN count(DISTINCT a) AS attribute_count
        """,
        params={"node_id": node_id, "attribute_name": attribute_name},
    )
    return results[0]["attribute_count"]


async def values_reachable_over_open_edges(db: InfrahubDatabase, node_id: str, attribute_name: str) -> list[Any]:
    """The attribute values a node still reads, following only open, active global edges."""
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[owning:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
        WHERE owning.branch = $global_branch AND owning.status = "active" AND owning.to IS NULL
        MATCH (a)-[value_edge:HAS_VALUE]->(value:AttributeValue)
        WHERE value_edge.branch = $global_branch AND value_edge.status = "active" AND value_edge.to IS NULL
        RETURN value.value AS value
        """,
        params={"node_id": node_id, "attribute_name": attribute_name, "global_branch": GLOBAL_BRANCH_NAME},
    )
    return [result["value"] for result in results]


async def tombstone_existence_only(db: InfrahubDatabase, node_id: str, branch: Branch, at: Timestamp) -> None:
    """Mark the owner deleted while leaving every field edge exactly as it was.

    The ordinary delete tombstones an attribute's edges alongside the existence edge, so both axes flip
    together and either one alone would reach the right answer. This builds the state where they
    disagree -- an owner no branch reads as live still holding an open, active global value edge --
    which is the orphan shape this feature repairs.
    """
    results = await db.execute_query(
        query="""
        MATCH (n:Node {uuid: $node_id})-[existing:IS_PART_OF]->(root:Root)
        WHERE existing.branch = $branch AND existing.status = "active" AND existing.to IS NULL
        SET existing.to = $at
        CREATE (n)-[:IS_PART_OF {branch: $branch, branch_level: $branch_level, status: "deleted", from: $at}]->(root)
        RETURN count(existing) AS tombstoned
        """,
        params={
            "node_id": node_id,
            "branch": branch.name,
            "branch_level": branch.hierarchy_level,
            "at": at.to_string(),
        },
    )
    assert results[0]["tombstoned"] == 1


async def tombstone_relationship_peer_edge(
    db: InfrahubDatabase, node_id: str, identifier: str, peer_id: str, at: Timestamp
) -> None:
    """Add a `deleted` global peer edge that supersedes the active one, leaving the active one open.

    A tombstone is a new, more recent edge rather than a rewrite of the one it supersedes -- the graph
    never holds a `deleted` edge where the `active` one it replaced has vanished. Both stay open, and
    which of them speaks for the branch is decided by the ordering, which is what puts the status under
    test here.
    """
    results = await db.execute_query(
        query="""
        MATCH (peer:Node {uuid: $peer_id})-[active:IS_RELATED]-(r:Relationship {name: $identifier})
        WHERE active.branch = $global_branch AND active.status = "active" AND active.to IS NULL
        AND EXISTS { MATCH (:Node {uuid: $node_id})-[:IS_RELATED]-(r) }
        CREATE (peer)-[:IS_RELATED {branch: $global_branch, branch_level: active.branch_level,
                                    status: "deleted", from: $at}]->(r)
        RETURN count(active) AS tombstoned
        """,
        params={
            "node_id": node_id,
            "identifier": identifier,
            "peer_id": peer_id,
            "global_branch": GLOBAL_BRANCH_NAME,
            "at": at.to_string(),
        },
    )
    assert results[0]["tombstoned"] == 1


async def remove_attribute_on_branch(
    db: InfrahubDatabase, node_id: str, attribute_name: str, branch: Branch, at: Timestamp
) -> None:
    """Mirror the owning edge with a branch-level `deleted` one, as a schema attribute removal does.

    A removal never closes the global edges; it writes a more specific `deleted` edge that wins under
    the removing branch's view only, which is what makes the field disappear there while the object
    goes on existing everywhere.
    """
    await db.execute_query(
        query="""
        MATCH (n:Node {uuid: $node_id})-[owning:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
        WHERE owning.branch = $global_branch AND owning.status = "active" AND owning.to IS NULL
        CREATE (n)-[:HAS_ATTRIBUTE {branch: $branch_name, branch_level: $branch_level, status: "deleted", from: $at}]->(a)
        """,
        params={
            "node_id": node_id,
            "attribute_name": attribute_name,
            "global_branch": GLOBAL_BRANCH_NAME,
            "branch_name": branch.name,
            "branch_level": branch.hierarchy_level,
            "at": at.to_string(),
        },
    )


async def pool_reservation_edges(db: InfrahubDatabase, pool_id: str, identifier: str) -> list[EdgeState]:
    """Every reservation edge a pool holds under one identifier, on any branch."""
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $pool_id})-[e:IS_RESERVED {identifier: $identifier}]->(:AttributeValue)
        RETURN type(e) AS edge_type, e.branch AS branch, e.status AS status,
               e.from AS from_time, e.to AS to_time, e.to_user_id AS to_user_id
        """,
        params={"pool_id": pool_id, "identifier": identifier},
    )
    return [EdgeState(**dict(result)) for result in results]


async def attribute_metadata(db: InfrahubDatabase, node_id: str, attribute_name: str) -> VertexMetadata:
    """The audit stamps on the attribute vertex reached from this node.

    Assumes a single :Node vertex with the `node_id` and a single linked :Attribute with the
    `attribute_name`.
    """
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(v:Attribute {name: $attribute_name})
        WITH DISTINCT v
        RETURN v.updated_at AS updated_at, v.updated_by AS updated_by,
           v.previous_updated_at AS previous_updated_at, v.previous_updated_by AS previous_updated_by
        """,
        params={"node_id": node_id, "attribute_name": attribute_name},
    )
    assert len(results) == 1, f"Expected a single {attribute_name} attribute for {node_id}, found {len(results)}"
    return VertexMetadata(**dict(results[0]))


async def relationship_metadata(db: InfrahubDatabase, node_id: str, identifier: str) -> VertexMetadata:
    """The audit stamps on the relationship vertex reached from this node.

    Assumes a single :Node vertex with the `node_id` and a single linked :Relationship with the
    `identifier`.
    """
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:IS_RELATED]-(v:Relationship {name: $identifier})
        WITH DISTINCT v
        RETURN v.updated_at AS updated_at, v.updated_by AS updated_by,
           v.previous_updated_at AS previous_updated_at, v.previous_updated_by AS previous_updated_by
        """,
        params={"node_id": node_id, "identifier": identifier},
    )
    return VertexMetadata(**dict(results[0]))
