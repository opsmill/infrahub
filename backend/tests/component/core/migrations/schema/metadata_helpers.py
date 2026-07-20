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
