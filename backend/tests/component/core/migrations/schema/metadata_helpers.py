"""Shared helpers for the schema-migration metadata tests.

These assert how a schema migration bumps the user-timestamp metadata (``updated_at``/``updated_by``)
stored on Node/Attribute/Relationship vertices, snapshots the prior values into
``previous_updated_at``/``previous_updated_by``, and how a merge-failure rollback restores them.
"""

from dataclasses import dataclass

from infrahub.database import InfrahubDatabase


@dataclass
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
    """Return the vertex metadata for the attribute whose HAS_ATTRIBUTE edge opened at ``edge_from``.

    Filtering on the edge's ``from`` time uniquely selects a freshly-(re)created attribute even when an
    earlier same-named attribute still exists on the node (e.g. a remove-then-add, or a rename). Pass the
    migration timestamp (``Timestamp.to_string()``).
    """
    results = await db.execute_query(
        query=(
            "MATCH (n:Node {uuid: $node_uuid})-[e:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name}) "
            "WHERE e.from = $edge_from "
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
