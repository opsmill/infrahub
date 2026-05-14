from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class SchemaSummary:
    """Snapshot of one SchemaNode/SchemaGeneric ``attributes`` and ``relationships`` map field name to uuid."""

    uuid: str
    is_generic: bool
    attributes: dict[str, str] = field(default_factory=dict)
    relationships: dict[str, str] = field(default_factory=dict)


class SchemaSummaryIndex:
    """Indexed view of ``SchemaSummaryQuery`` results, look-up by either ``kind`` or ``uuid``.

    Internal ``kind`` and ``uuid`` maps point at the *same* ``SchemaSummary`` instances — they
    are alternate keys on the same underlying rows.
    """

    def __init__(self) -> None:
        self._by_kind: dict[str, SchemaSummary] = {}
        self._by_uuid: dict[str, SchemaSummary] = {}

    def add(self, kind: str, summary: SchemaSummary) -> None:
        """Record a summary under both its ``kind`` and ``uuid`` keys."""
        self._by_kind[kind] = summary
        self._by_uuid[summary.uuid] = summary

    def get_summary_by_kind(self, kind: str) -> SchemaSummary | None:
        """Return the ``SchemaSummary`` indexed under ``kind``, or ``None`` if not present."""
        return self._by_kind.get(kind)

    def get_summary_by_uuid(self, uuid: str) -> SchemaSummary | None:
        """Return the ``SchemaSummary`` indexed under ``uuid``, or ``None`` if not present."""
        return self._by_uuid.get(uuid)

    def get_kinds(self) -> set[str]:
        """Return the set of all known ``kind`` keys."""
        return set(self._by_kind.keys())

    def __len__(self) -> int:
        return len(self._by_kind)


class SchemaSummaryQuery(Query):
    """Fast lookup of SchemaNode / SchemaGeneric on a branch with their fields.

    When ``kind_filter`` is supplied (a list of ``(namespace, name)`` tuples), results are filtered
    to those kinds. When ``uuid_filter`` is also supplied, any node whose ``uuid`` is in the list is
    additionally included regardless of its current ``(namespace, name)``
    """

    name: str = "existing_schema_nodes"
    type: QueryType = QueryType.READ

    def __init__(
        self,
        kind_filter: list[tuple[str, str]] | None = None,
        uuid_filter: list[str] | None = None,
        attribute_names: list[str] | None = None,
        relationship_names: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.kind_filter = kind_filter
        self.uuid_filter = uuid_filter
        # ``None`` -> include all attribute / relationship children.
        # ``[]``   -> include none (skip the name-keyed dicts entirely).
        # ``[...]``-> include only children whose ``name`` value is in the list.
        self.attribute_names = attribute_names
        self.relationship_names = relationship_names
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_params)
        self.params["attribute_names"] = self.attribute_names
        self.params["relationship_names"] = self.relationship_names
        self.params["filter_uuids"] = self.uuid_filter or None

        if self.kind_filter:
            filter_namespaces: set[str] = set()
            filter_names: set[str] = set()
            for namespace, name in self.kind_filter:
                filter_namespaces.add(namespace)
                filter_names.add(name)
            self.params["filter_namespaces"] = list(filter_namespaces)
            self.params["filter_names"] = list(filter_names)
            # Prefilter matches a parent that EITHER has (namespace, name) in the filter OR has
            # its uuid in $filter_uuids
            filter_kinds: set[str] = {f"{namespace}{name}" for namespace, name in self.kind_filter}
            self.params["filter_kinds"] = list(filter_kinds)
            prefilter_clause = """
// ---------------------------
// Prefilter: by (namespace, name) OR by uuid
// ---------------------------
CALL () {
    MATCH (n:SchemaNode|SchemaGeneric)
        -[:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})
        -[:HAS_VALUE]->(av_ns:AttributeValue)
    WHERE av_ns.value IN $filter_namespaces
    WITH DISTINCT n
    MATCH (n)
        -[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})
        -[:HAS_VALUE]->(av_name:AttributeValue)
    WHERE av_name.value IN $filter_names
    RETURN DISTINCT n
    UNION
    MATCH (n:SchemaNode|SchemaGeneric)
    WHERE $filter_uuids IS NOT NULL AND n.uuid IN $filter_uuids
    RETURN DISTINCT n
}
WITH DISTINCT n
            """
        else:
            self.params["filter_kinds"] = None
            self.params["filter_namespaces"] = None
            self.params["filter_names"] = None
            prefilter_clause = "MATCH (n:SchemaNode|SchemaGeneric)"

        self.add_to_query(prefilter_clause)
        query = """
// ---------------------------
// Parent: must have a latest-active IS_PART_OF on the branch
// ---------------------------
CALL (n) {
    MATCH (n)-[r:IS_PART_OF]->(:Root)
    WHERE %(branch_filter)s
    RETURN r AS is_part_of_r
    ORDER BY r.branch_level DESC, r.from DESC
    LIMIT 1
}
WITH n, is_part_of_r
WHERE is_part_of_r.status = "active"
// ---------------------------
// Parent: name value
// ---------------------------
CALL (n) {
    MATCH (n)-[r:HAS_ATTRIBUTE]->(name_attr:Attribute {name: "name"})
    WHERE %(branch_filter)s
    RETURN name_attr
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
CALL (name_attr) {
    MATCH (name_attr)-[r:HAS_VALUE]->(av:AttributeValue)
    WHERE %(branch_filter)s
    RETURN av.value AS name_value
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
// ---------------------------
// Parent: namespace value
// ---------------------------
CALL (n) {
    MATCH (n)-[r:HAS_ATTRIBUTE]->(ns_attr:Attribute {name: "namespace"})
    WHERE %(branch_filter)s
    RETURN ns_attr
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
CALL (ns_attr) {
    MATCH (ns_attr)-[r:HAS_VALUE]->(av:AttributeValue)
    WHERE %(branch_filter)s
    RETURN av.value AS namespace_value
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH
    n,
    namespace_value + name_value AS kind,
    "SchemaGeneric" IN labels(n) AS is_generic
WHERE
    ($filter_kinds IS NULL AND $filter_uuids IS NULL)
    OR ($filter_kinds IS NOT NULL AND kind IN $filter_kinds)
    OR ($filter_uuids IS NOT NULL AND n.uuid IN $filter_uuids)

// ---------------------------
// Phase 1: SchemaAttributes
// Start with all possible SchemaAttributes for this schema
// ---------------------------
OPTIONAL MATCH (n)-[:IS_RELATED]->(:Relationship {name: "schema__node__attributes"})
    <-[:IS_RELATED]-(schema_attr:SchemaAttribute)
    -[:HAS_ATTRIBUTE]-(:Attribute {name: "name"})
    -[:HAS_VALUE]->(attr_name_value)
WHERE $attribute_names IS NULL OR attr_name_value.value IN $attribute_names
WITH DISTINCT n, kind, is_generic, schema_attr

// ---------------------------
// get the name of the SchemaAttribute
// ---------------------------
CALL (schema_attr) {
    OPTIONAL MATCH (schema_attr)-[r:HAS_ATTRIBUTE]->(attr_name:Attribute {name: "name"})
    WHERE %(branch_filter)s
    RETURN attr_name
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
CALL (attr_name) {
    OPTIONAL MATCH (attr_name)-[r:HAS_VALUE]->(av:AttributeValue)
    WHERE %(branch_filter)s
    RETURN av.value AS field_name_value
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, kind, is_generic, schema_attr, field_name_value
WHERE schema_attr IS NULL OR $attribute_names IS NULL OR field_name_value IN $attribute_names

// ---------------------------
// check if relationship to SchemaAttribute is active
// ---------------------------
CALL (n, schema_attr) {
    OPTIONAL MATCH (n)-[r:IS_RELATED]->(rel_vertex:Relationship {name: "schema__node__attributes"})
    WHERE %(branch_filter)s
    AND exists((rel_vertex)<-[:IS_RELATED]-(schema_attr))
    WITH rel_vertex, r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    RETURN rel_vertex, r.status AS parent_edge_status
}
WITH n, kind, is_generic, rel_vertex, schema_attr, field_name_value
WHERE parent_edge_status = "active" OR parent_edge_status IS NULL
CALL (rel_vertex, schema_attr) {
    OPTIONAL MATCH (rel_vertex)<-[r:IS_RELATED]-(schema_attr)
    WHERE %(branch_filter)s
    WITH r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    RETURN r.status AS child_edge_status
}
WITH n, kind, is_generic, schema_attr, field_name_value
WHERE child_edge_status = "active" OR child_edge_status IS NULL

// ---------------------------
// put the SchemaAttribute UUID and name into a list — gated by $attribute_names
//   NULL   -> include every active attribute
//   []     -> include none
//   [...]  -> include only attributes whose name is in the list
// ---------------------------
WITH
    n, kind, is_generic,
    collect(
        CASE
            WHEN schema_attr IS NOT NULL
            THEN [schema_attr.uuid, field_name_value]
        END
    ) AS attributes

// ---------------------------
// Phase 2: SchemaRelationships
// Start with all possible SchemaRelationships for this schema, pre-filtered by name (non-branch-aware)
// ---------------------------
OPTIONAL MATCH (n)-[:IS_RELATED]->(:Relationship {name: "schema__node__relationships"})
    <-[:IS_RELATED]-(schema_rel:SchemaRelationship)
    -[:HAS_ATTRIBUTE]-(:Attribute {name: "name"})
    -[:HAS_VALUE]->(rel_name_value)
WHERE $relationship_names IS NULL OR rel_name_value.value IN $relationship_names
WITH DISTINCT n, kind, is_generic, attributes, schema_rel

// ---------------------------
// get the on-branch name of the SchemaRelationship
// ---------------------------
CALL (schema_rel) {
    OPTIONAL MATCH (schema_rel)-[r:HAS_ATTRIBUTE]->(rel_name:Attribute {name: "name"})
    WHERE %(branch_filter)s
    RETURN rel_name
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
CALL (rel_name) {
    OPTIONAL MATCH (rel_name)-[r:HAS_VALUE]->(av:AttributeValue)
    WHERE %(branch_filter)s
    RETURN av.value AS field_name_value
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, kind, is_generic, attributes, schema_rel, field_name_value
WHERE schema_rel IS NULL OR $relationship_names IS NULL OR field_name_value IN $relationship_names

// ---------------------------
// check if relationship to SchemaRelationship is active
// ---------------------------
CALL (n, schema_rel) {
    OPTIONAL MATCH (n)-[r:IS_RELATED]->(rel_vertex:Relationship {name: "schema__node__relationships"})
    WHERE %(branch_filter)s
    AND exists((rel_vertex)<-[:IS_RELATED]-(schema_rel))
    WITH rel_vertex, r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    RETURN rel_vertex, r.status AS rel_parent_edge_status
}
WITH n, kind, is_generic, attributes, rel_vertex, schema_rel, field_name_value
WHERE rel_parent_edge_status = "active" OR rel_parent_edge_status IS NULL
CALL (rel_vertex, schema_rel) {
    OPTIONAL MATCH (rel_vertex)<-[r:IS_RELATED]-(schema_rel)
    WHERE %(branch_filter)s
    WITH r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    RETURN r.status AS rel_child_edge_status
}
WITH n, kind, is_generic, attributes, schema_rel, field_name_value
WHERE rel_child_edge_status = "active" OR rel_child_edge_status IS NULL

// ---------------------------
// put the SchemaRelationship UUID and name into a list — gated by $relationship_names
// (same NULL / [] / [...] semantics as $attribute_names above)
// ---------------------------
WITH
    n, kind, is_generic, attributes,
    collect(
        CASE
            WHEN schema_rel IS NOT NULL
            THEN [schema_rel.uuid, field_name_value]
        END
    ) AS relationships

WITH n.uuid AS uuid, kind, is_generic, attributes, relationships
        """ % {"branch_filter": branch_filter}

        self.add_to_query(query)
        self.return_labels = ["kind", "is_generic", "uuid", "attributes", "relationships"]

    def get_summaries(self) -> SchemaSummaryIndex:
        """Return a ``SchemaSummaryIndex`` keyed by both ``kind`` and ``uuid``."""
        index = SchemaSummaryIndex()
        for result in self.get_results():
            kind = result.get_as_type("kind", return_type=str)
            attributes_raw = cast("list[list[str]]", result.get("attributes") or [])
            relationships_raw = cast("list[list[str]]", result.get("relationships") or [])
            summary = SchemaSummary(
                uuid=result.get_as_type("uuid", return_type=str),
                is_generic=result.get_as_type("is_generic", return_type=bool),
                attributes={pair[1]: pair[0] for pair in attributes_raw if pair and pair[1] is not None},
                relationships={pair[1]: pair[0] for pair in relationships_raw if pair and pair[1] is not None},
            )
            index.add(kind=kind, summary=summary)
        return index
