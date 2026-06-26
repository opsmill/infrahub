from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class SchemaAttributeRewrite:
    """One rewrite target for :class:`BulkRewriteSchemaAttributeQuery`.

    ``parent_name`` / ``parent_namespace`` always identify the parent SchemaNode
    or SchemaGeneric. When ``relationship_name`` is ``None`` the attribute being
    rewritten lives directly on the parent (``parent``-[:HAS_ATTRIBUTE]->(attr));
    when it is set, the rewrite target is the SchemaRelationship reached via
    ``parent``-[:IS_RELATED]-()-[:IS_RELATED]-(SchemaRelationship {name = relationship_name})``.
    """

    parent_name: str
    parent_namespace: str
    attribute_name: str
    new_value: str
    relationship_name: str | None = None


class BulkRewriteSchemaAttributeQuery(Query):
    """Rewrite all ``HAS_VALUE`` edges linking an Attribute to an AttributeValue.

    Each ``rewrite`` row is a :class:`SchemaAttributeRewrite`. ``parent_name`` /
    ``parent_namespace`` identify the parent SchemaNode or SchemaGeneric. When
    ``relationship_name`` is ``None`` the rewrite target is an Attribute directly
    on the parent; when set, it's the matching attribute on the SchemaRelationship
    reached via ``parent`` → IS_RELATED → SchemaRelationship.

    Idempotent: if the target ``AttributeValue`` already has ``new_value`` the
    row is a no-op. Otherwise the new edge inherits the old edge's properties
    (preserving its ``from`` time so past-timestamp queries see the new value),
    the old edge is hard-deleted, and any orphaned old ``AttributeValue`` is
    detach-deleted.
    """

    name = "bulk_rewrite_schema_attribute"
    type: QueryType = QueryType.WRITE
    insert_return: bool = False

    def __init__(
        self,
        rewrites: list[SchemaAttributeRewrite],
        default_branch_name: str,
        **kwargs: Any,
    ) -> None:
        self.rewrites = rewrites
        self.default_branch_name = default_branch_name
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["rewrites"] = [asdict(rw) for rw in self.rewrites]
        self.params["default_branch"] = self.default_branch_name
        query = """
UNWIND $rewrites AS rw
// --------------------
// all possible parent vertexes
// --------------------
MATCH (parent:SchemaNode|SchemaGeneric)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(:AttributeValue {value: rw.parent_name})
WITH DISTINCT parent, rw
CALL (parent) {
    MATCH (parent)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})
        -[r:HAS_VALUE]->(av_name:AttributeValue)
    WHERE r.branch = $default_branch
    AND r.status = "active"
    AND r.to IS NULL
    RETURN av_name.value AS name_value
    ORDER BY r.from DESC
    LIMIT 1
}
CALL (parent) {
    MATCH (parent)-[:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})
        -[r:HAS_VALUE]->(av_ns:AttributeValue)
    WHERE r.branch = $default_branch
    AND r.status = "active"
    AND r.to IS NULL
    RETURN av_ns.value AS namespace_value
    ORDER BY r.from DESC
    LIMIT 1
}
// --------------------
// filter to the correct parent vertexes
// --------------------
WITH parent, rw
WHERE name_value = rw.parent_name AND namespace_value = rw.parent_namespace
// --------------------
// pick the vertex whose attribute we'll rewrite: either the parent itself
// (relationship_name is null), or the active SchemaRelationship with the
// given name/identifier. If relationship_name is set but no active path is
// found, vertex_to_update resolves to NULL and the row is dropped.
// --------------------
CALL (parent, rw) {
    OPTIONAL MATCH (parent)-[r1:IS_RELATED]-(:Relationship)
        -[r2:IS_RELATED]-(sr:SchemaRelationship)
        -[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})
        -[r3:HAS_VALUE]->(:AttributeValue {value: rw.relationship_name})
    WHERE rw.relationship_name IS NOT NULL
    AND r1.branch = $default_branch AND r1.status = "active" AND r1.to IS NULL
    AND r2.branch = $default_branch AND r2.status = "active" AND r2.to IS NULL
    AND r3.branch = $default_branch AND r3.status = "active" AND r3.to IS NULL
    RETURN sr
    ORDER BY r3.from DESC, r2.from DESC, r1.from DESC
    LIMIT 1
}
WITH rw,
    CASE WHEN rw.relationship_name IS NULL THEN parent ELSE sr END AS vertex_to_update
WHERE vertex_to_update IS NOT NULL
// --------------------
// get the Attribute, HAS_VALUE, and AttributeValue groups to update
// --------------------
CALL (vertex_to_update, rw) {
    MATCH (vertex_to_update)-[:HAS_ATTRIBUTE]->(attr:Attribute {name: rw.attribute_name})
        -[hv_old:HAS_VALUE]->(av_old:AttributeValue)
    RETURN attr, hv_old, av_old
}
// --------------------
// update all the HAS_VALUE edges from the identified Attribute vertex to the old value
// regardless of time, branch, or active-ness
// --------------------
WITH DISTINCT rw, attr, hv_old, av_old
CALL (rw, av_old) {
    MERGE (av_new:AttributeValue {value: rw.new_value, is_default: av_old.is_default})
    RETURN av_new
    LIMIT 1
}
WITH attr, hv_old, av_old, av_new
WHERE av_new.value <> av_old.value
CREATE (attr)-[hv_new:HAS_VALUE]->(av_new)
SET hv_new = properties(hv_old)
DELETE hv_old
// --------------------
// detach delete orphaned AttributeValue vertices
// --------------------
WITH DISTINCT av_old
CALL (av_old) {
    WITH av_old
    WHERE NOT exists((av_old)<-[]-())
    DETACH DELETE av_old
}
        """
        self.add_to_query(query)
