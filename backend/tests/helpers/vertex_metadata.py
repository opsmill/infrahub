"""Shared helpers for the vertex-metadata tests.

These assert how a schema migration bumps the user-timestamp metadata (``updated_at``/``updated_by``)
stored on Node/Attribute/Relationship vertices, snapshots the prior values into
``previous_updated_at``/``previous_updated_by``, and how a merge-failure rollback restores them.

Also includes functions for verifying metadata properties of vertexes based on their linked default
and global branch edges.
"""

from dataclasses import dataclass

from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class VertexMetadata:
    """The user-timestamp metadata stored directly on a Node/Attribute/Relationship vertex.

    ``previous_updated_at``/``previous_updated_by`` hold the snapshot a schema migration or merge
    records before bumping ``updated_at``/``updated_by``, so a merge-failure rollback can restore them.
    """

    updated_at: str | None = None
    updated_by: str | None = None
    previous_updated_at: str | None = None
    previous_updated_by: str | None = None


async def get_node_vertex_metadata(db: InfrahubDatabase, node_uuid: str) -> VertexMetadata:
    """Return the vertex metadata for the single Node vertex identified by ``node_uuid``.

    Expects exactly one Node vertex with the uuid; callers that duplicate a node (e.g. a kind change
    that leaves two same-uuid vertices) must disambiguate themselves rather than use this helper.
    """
    results = await db.execute_query(
        query=(
            "MATCH (n:Node {uuid: $node_uuid}) "
            "RETURN n.updated_at AS updated_at, n.updated_by AS updated_by, "
            "n.previous_updated_at AS previous_updated_at, n.previous_updated_by AS previous_updated_by"
        ),
        params={"node_uuid": node_uuid},
    )
    assert len(results) == 1, f"Expected exactly one Node vertex for {node_uuid}, found {len(results)}"
    row = results[0]
    return VertexMetadata(
        updated_at=row["updated_at"],
        updated_by=row["updated_by"],
        previous_updated_at=row["previous_updated_at"],
        previous_updated_by=row["previous_updated_by"],
    )


async def get_attribute_vertex_metadata(
    db: InfrahubDatabase, node_uuid: str, attribute_name: str, edge_from: str
) -> VertexMetadata:
    """Return the vertex metadata for the attribute whose HAS_ATTRIBUTE edge opened at ``edge_from``."""
    results = await db.execute_query(
        query=(
            'MATCH (n:Node {uuid: $node_uuid})-[e:HAS_ATTRIBUTE {status: "active"}]->(a:Attribute {name: $attribute_name}) '
            "WHERE e.from = $edge_from AND e.to IS NULL "
            "RETURN a.updated_at AS updated_at, a.updated_by AS updated_by, "
            "a.previous_updated_at AS previous_updated_at, a.previous_updated_by AS previous_updated_by"
        ),
        params={"node_uuid": node_uuid, "attribute_name": attribute_name, "edge_from": edge_from},
    )
    assert len(results) == 1, (
        f"Expected exactly one '{attribute_name}' attribute opened at {edge_from} for {node_uuid}, found {len(results)}"
    )
    row = results[0]
    return VertexMetadata(
        updated_at=row["updated_at"],
        updated_by=row["updated_by"],
        previous_updated_at=row["previous_updated_at"],
        previous_updated_by=row["previous_updated_by"],
    )


async def branch_metadata_fingerprint(db: InfrahubDatabase, branch_name: str) -> list[tuple]:
    """Snapshot the user-timestamp metadata of every Node/Attribute/Relationship vertex on a branch.

    The vertex-metadata analogue of ``branch_edge_fingerprint``: two snapshots compare equal only when
    every vertex's ``updated_at``/``updated_by`` and ``previous_updated_at``/``previous_updated_by`` are
    identical, so an empty diff between a pre-change and a post-rollback snapshot proves the rollback
    restored the metadata that a schema migration or merge bumped (and cleared the snapshot).
    """
    results = await db.execute_query(
        query=(
            "MATCH (v)-[{branch: $branch}]-() "
            "WHERE v:Node OR v:Attribute OR v:Relationship "
            "RETURN DISTINCT elementId(v) AS id, v.updated_at AS updated_at, v.updated_by AS updated_by, "
            "v.previous_updated_at AS previous_updated_at, v.previous_updated_by AS previous_updated_by"
        ),
        params={"branch": branch_name},
    )
    return sorted(
        (
            row["id"],
            row["updated_at"] or "",
            row["updated_by"] or "",
            row["previous_updated_at"] or "",
            row["previous_updated_by"] or "",
        )
        for row in results
    )


async def branch_edge_fingerprint(db: InfrahubDatabase, branch_name: str) -> list[tuple]:
    """Snapshot every edge on a branch, keyed on endpoints, timestamps and status.

    Two snapshots compare equal only when the branch's edges are identical, so an empty diff between a
    pre-change and a post-rollback snapshot proves the rollback restored the branch exactly.
    """
    results = await db.execute_query(
        query=(
            "MATCH (src)-[r {branch: $branch}]->(dst) "
            "RETURN type(r) AS edge_type, elementId(src) AS src, elementId(dst) AS dst, "
            "r.from AS edge_from, r.to AS edge_to, r.status AS status"
        ),
        params={"branch": branch_name},
    )
    return sorted(
        (
            row["edge_type"],
            row["src"],
            row["dst"],
            row["edge_from"] or "",
            row["edge_to"] or "",
            row["status"] or "",
        )
        for row in results
    )


# ---------------------------------------------------------------------------
# Deriving a vertex's metadata from its edges
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VertexUserMetadata:
    """The four user-metadata properties the recompute derives."""

    created_at: str | None
    created_by: str | None
    updated_at: str | None
    updated_by: str | None


def _event(value: list | None) -> tuple[str | None, str | None]:
    if not value:
        return (None, None)
    return (value[0], value[1])


async def recompute_vertex_metadata(db: InfrahubDatabase, element_id: str) -> VertexUserMetadata | None:
    """Derive what ``element_id``'s metadata should be from the level-1 edges around it.

    Returns ``None`` for a vertex with no ``branch_level = 1`` edge at all, which has no presence a
    default-branch reader could see and so nothing to say about.
    """
    query = """
MATCH (v) WHERE elementId(v) = $element_id
CALL (v) {
    WITH v WHERE v:Node
    CALL (v) {
        MATCH (:Node {uuid: v.uuid})-[r:IS_PART_OF]->(:Root)
        WHERE r.branch_level = 1
        WITH [r.from, r.from_user_id] AS event
        ORDER BY event[0] ASC, event[1] ASC
        RETURN head(collect(event)) AS created
    }
    CALL (v) {
        MATCH (v)-[link:HAS_ATTRIBUTE|IS_RELATED]-(field:Attribute|Relationship)
        WHERE link.branch_level = 1
        OPTIONAL MATCH (field)-[e]-()
        WHERE link.status = "active" AND link.to IS NULL AND e.branch_level = 1
        UNWIND [
            [link.from, link.from_user_id], [link.to, link.to_user_id],
            [e.from, e.from_user_id], [e.to, e.to_user_id]
        ] AS event
        WITH event WHERE event[0] IS NOT NULL
        ORDER BY event[0] DESC, event[1] DESC
        RETURN head(collect(event)) AS updated
    }
    RETURN created, updated
  UNION
    WITH v WHERE NOT v:Node
    CALL (v) {
        MATCH (v)-[e]-()
        WHERE e.branch_level = 1
        WITH [e.from, e.from_user_id] AS event
        ORDER BY event[0] ASC, event[1] ASC
        RETURN head(collect(event)) AS created
    }
    CALL (v) {
        MATCH (v)-[e]-()
        WHERE e.branch_level = 1
        UNWIND [[e.from, e.from_user_id], [e.to, e.to_user_id]] AS event
        WITH event WHERE event[0] IS NOT NULL
        ORDER BY event[0] DESC, event[1] DESC
        RETURN head(collect(event)) AS updated
    }
    RETURN created, updated
}
RETURN created, updated
    """
    results = await db.execute_query(query=query, params={"element_id": element_id})
    if not results:
        return None
    created_at, created_by = _event(results[0]["created"])
    updated_at, updated_by = _event(results[0]["updated"])
    if created_at is None and updated_at is None:
        return None
    return VertexUserMetadata(
        created_at=created_at,
        created_by=created_by,
        updated_at=updated_at or created_at,
        updated_by=updated_by if updated_at else created_by,
    )


async def get_vertex_user_metadata(db: InfrahubDatabase, element_id: str) -> VertexUserMetadata:
    """Read the four metadata properties stored on ``element_id``.

    Raises:
        AssertionError: If no vertex carries that element id.

    """
    query = """
MATCH (v) WHERE elementId(v) = $element_id
RETURN v.created_at AS created_at, v.created_by AS created_by,
       v.updated_at AS updated_at, v.updated_by AS updated_by
    """
    results = await db.execute_query(query=query, params={"element_id": element_id})
    if not results:
        raise AssertionError(f"no vertex with element id {element_id}")
    return VertexUserMetadata(
        created_at=results[0]["created_at"],
        created_by=results[0]["created_by"],
        updated_at=results[0]["updated_at"],
        updated_by=results[0]["updated_by"],
    )


async def get_node_vertex_element_ids(db: InfrahubDatabase, node_uuid: str) -> list[str]:
    """Every Node vertex carrying ``node_uuid``, in a stable order. A migration leaves more than one."""
    query = """
MATCH (n:Node {uuid: $node_uuid})
RETURN elementId(n) AS element_id
ORDER BY element_id
    """
    results = await db.execute_query(query=query, params={"node_uuid": node_uuid})
    return [result["element_id"] for result in results]


async def assert_vertex_metadata_matches_recompute(
    db: InfrahubDatabase, element_id: str, description: str
) -> VertexUserMetadata:
    """Assert the metadata stored on ``element_id`` equals the recompute.

    Raises:
        AssertionError: If any of the four properties differs from the recompute, or if the vertex
            has no level-1 edge to recompute from. The message names each field that differs.

    """
    stored = await get_vertex_user_metadata(db=db, element_id=element_id)
    recomputed = await recompute_vertex_metadata(db=db, element_id=element_id)
    if recomputed is None:
        raise AssertionError(f"{description} has no level-1 edge to recompute from")
    mismatches = [
        f"{name}: stored={getattr(stored, name)!r}, recomputed={getattr(recomputed, name)!r}"
        for name in ("created_at", "created_by", "updated_at", "updated_by")
        if getattr(stored, name) != getattr(recomputed, name)
    ]
    if mismatches:
        raise AssertionError(f"{description} metadata disagrees with the recompute -- " + "; ".join(mismatches))
    return stored
