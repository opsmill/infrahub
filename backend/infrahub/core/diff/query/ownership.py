from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import InfrahubKind
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.ownership.models import HolderKey, HolderKind
from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.database import InfrahubDatabase

OWNER_STATE_EDGE_TYPES = (DatabaseEdgeType.HAS_OWNER, DatabaseEdgeType.HAS_NO_OWNER)

# The path from the node `n` to the vertex that holds the owner edges, for each kind of holder.
ATTRIBUTE_PATTERN = '(n:Node)-[:HAS_ATTRIBUTE]->(holder:Attribute {branch_support: "aware"})'
HOLDER_PATTERNS: dict[HolderKind, str] = {
    HolderKind.NODE: "(n:Node)",
    HolderKind.FIELD_SET: "(n:Node)-[:HAS_OWNER_SET]->(holder:OwnerSet)",
    HolderKind.TARGET_SET: "(n:Node)-[:HAS_TARGET_OWNER_SET]->(holder:OwnerSet)",
    HolderKind.ATTRIBUTE: ATTRIBUTE_PATTERN,
    HolderKind.SOURCES: "(n:Node)",
}


def holder_edge_patterns() -> Iterator[tuple[HolderKind, str, DatabaseEdgeType]]:
    """Yield each kind of holder with the path to its vertex and one type of the edges that hold its state.

    The vertex is `holder` in the path, and the node `n` when the path has no `holder`.
    """
    for holder_kind, pattern in HOLDER_PATTERNS.items():
        edge_types = (DatabaseEdgeType.HAS_SOURCE,) if holder_kind is HolderKind.SOURCES else OWNER_STATE_EDGE_TYPES
        for edge_type in edge_types:
            yield holder_kind, pattern, edge_type


def template_mark_patterns() -> Iterator[tuple[HolderKind, str]]:
    """Yield each kind of holder that can hold the mark of a copy from an object template, with the path to its vertex."""
    for holder_kind, pattern in HOLDER_PATTERNS.items():
        if holder_kind not in {HolderKind.TARGET_SET, HolderKind.SOURCES}:
            yield holder_kind, pattern


@dataclass(frozen=True)
class OwnerHolderChange:
    node_uuid: str
    node_kind: str
    node_db_id: str
    holder: HolderKey
    holder_uuid: str
    """The UUID of the attribute for the owners of an attribute, else the UUID of the node."""

    changed_at: Timestamp


class DiffOwnerHoldersQuery(Query):
    """List the holders whose owner edges or source edges changed on one branch within a time range.

    The owner edges include the mark of a copy from an object template.
    """

    name = "diff_owner_holders"
    type = QueryType.READ
    insert_return = False

    def __init__(
        self,
        from_time: Timestamp,
        to_time: Timestamp,
        node_uuids: list[str] | None = None,
        node_kinds: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.from_time = from_time
        self.to_time = to_time
        self.node_uuids = node_uuids
        self.node_kinds = node_kinds
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        link_filter, link_params = self.branch.get_query_filter_path(at=self.to_time, variable_name="link")
        self.params.update(link_params)
        self.params.update(
            {
                "branch_name": self.branch.name,
                "from_time": self.from_time.to_string(),
                "to_time": self.to_time.to_string(),
                "node_uuids": self.node_uuids,
                "node_kinds": self.node_kinds,
            }
        )
        # A scoped query starts from the nodes, and any other one from the index on the branch of each edge type.
        if self.node_uuids is None:
            hint, scope = "USING INDEX r:{edge_type}(branch)", ""
        else:
            hint, scope = "USING INDEX n:Node(uuid)", "AND n.uuid IN $node_uuids"
        edge_patterns = [(*edge_pattern, hint) for edge_pattern in holder_edge_patterns()] + [
            (holder_kind, pattern, DatabaseEdgeType.HAS_OWNER_SOURCE, hint)
            for holder_kind, pattern in template_mark_patterns()
        ]
        # The reads hide a repository owner from the upgrade, so its edges cannot give a change.
        peer_filters = {DatabaseEdgeType.HAS_OWNER: f"AND NOT peer:{InfrahubKind.GENERICREPOSITORY}"}
        patterns = [
            f"""
    MATCH {pattern}-[r:{edge_type.value}]->(peer)
    {edge_hint.format(edge_type=edge_type.value)}
    WHERE r.branch = $branch_name {scope} {peer_filters.get(edge_type, "")}
    AND (($from_time <= r.from < $to_time) OR ($from_time <= r.to < $to_time))
    RETURN n, "{holder_kind.value}" AS holder_kind, {"holder" if "holder" in pattern else "NULL"} AS holder, r"""
            for holder_kind, pattern, edge_type, edge_hint in edge_patterns
        ]
        query = """
CALL () {%(patterns)s
}
// A kind migration links the vertices of one UUID to the same holder, so only the latest link on the branch counts
CALL (n, holder) {
    OPTIONAL MATCH (linked:Node)-[link:HAS_ATTRIBUTE|HAS_OWNER_SET|HAS_TARGET_OWNER_SET]->(holder)
    WHERE linked.uuid = n.uuid AND %(link_filter)s
    RETURN linked
    ORDER BY link.branch_level DESC, link.from DESC, link.status ASC
    LIMIT 1
}
// The holder of the owners or the sources of a node is the node, so the latest link of the node to the root counts
CALL (n, holder) {
    OPTIONAL MATCH (vertex:Node {uuid: n.uuid})-[link:IS_PART_OF]->(:Root)
    WHERE holder IS NULL AND %(link_filter)s
    RETURN vertex
    ORDER BY link.branch_level DESC, link.from DESC, link.status ASC
    LIMIT 1
}
WITH n, holder_kind, holder, r
WHERE (linked IS NULL OR linked = n) AND (vertex IS NULL OR vertex = n)
WITH n, holder_kind, holder,
    CASE WHEN r.to IS NOT NULL AND $from_time <= r.to < $to_time THEN r.to ELSE r.from END AS changed_at
WHERE (holder_kind = "attribute" OR n.branch_support = "aware")
AND ($node_kinds IS NULL OR n.kind IN $node_kinds)
RETURN n.uuid AS node_uuid, n.kind AS node_kind, %(id_func)s(n) AS node_db_id, holder_kind,
    CASE holder_kind WHEN "attribute" THEN holder.name ELSE holder.attribute END AS attribute_name,
    holder.identifier AS identifier, holder.direction AS direction,
    coalesce(holder.uuid, n.uuid) AS holder_uuid, max(changed_at) AS changed_at
        """ % {
            "patterns": "\n    UNION ALL".join(patterns),
            "link_filter": link_filter,
            "id_func": db.get_id_function_name(),
        }
        self.add_to_query(query)
        self.return_labels = [
            "node_uuid",
            "node_kind",
            "node_db_id",
            "holder_kind",
            "attribute_name",
            "identifier",
            "direction",
            "holder_uuid",
            "changed_at",
        ]

    def get_changes(self) -> list[OwnerHolderChange]:
        return [
            OwnerHolderChange(
                node_uuid=result.get_as_type("node_uuid", str),
                node_kind=result.get_as_type("node_kind", str),
                node_db_id=result.get_as_type("node_db_id", str),
                holder=HolderKey(
                    kind=HolderKind(result.get_as_type("holder_kind", str)),
                    attribute=result.get_as_optional_type("attribute_name", str),
                    identifier=result.get_as_optional_type("identifier", str),
                    direction=result.get_as_optional_type("direction", str),
                ),
                holder_uuid=result.get_as_type("holder_uuid", str),
                changed_at=Timestamp(result.get_as_type("changed_at", str)),
            )
            for result in self.get_results()
        ]
