from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import RelationshipDirection
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.schema.relationship_schema import RelationshipSchema
    from infrahub.core.schema.virtual_relationship_schema import VirtualRelationshipSchema
    from infrahub.database import InfrahubDatabase


def _get_arrows_for_direction(direction: RelationshipDirection) -> tuple[str, str]:
    """Return (left_arrow, right_arrow) for a relationship based on its direction."""
    if direction == RelationshipDirection.OUTBOUND:
        return "-", "->"
    if direction == RelationshipDirection.INBOUND:
        return "<-", "-"
    # BIDIR: use undirected matching
    return "-", "-"


def _build_match_pattern(
    segments: list[str],
    relationship_schemas: list[RelationshipSchema],
    params: dict[str, Any],
) -> tuple[str, str]:
    """Build the Cypher MATCH path pattern and return (pattern, rel_refs_csv).

    Each hop produces two IS_RELATED edges: source -> Relationship node -> peer node.
    """
    match_parts = ["(source:Node { uuid: $source_id })"]

    for i, (_segment, rel_schema) in enumerate(zip(segments, relationship_schemas, strict=True)):
        identifier = rel_schema.get_identifier()
        param_name = f"seg{i}_id"
        params[param_name] = identifier

        left_arrow, right_arrow = _get_arrows_for_direction(rel_schema.direction)

        rel_node_name = f"rl{i}"
        hop_name = "target" if i == len(segments) - 1 else f"hop{i}"

        match_parts.append(f"{left_arrow}[r{i * 2}:IS_RELATED]{right_arrow}")
        match_parts.append(f"({rel_node_name}:Relationship {{name: ${param_name}}})")
        match_parts.append(f"{left_arrow}[r{i * 2 + 1}:IS_RELATED]{right_arrow}")
        match_parts.append(f"({hop_name}:Node)")

    match_pattern = "".join(match_parts)
    num_rels = len(segments) * 2
    rel_refs = ", ".join(f"r{i}" for i in range(num_rels))
    return match_pattern, rel_refs


class VirtualRelationshipGetPeersQuery(Query):
    """Multi-hop traversal query that follows a virtual relationship path to collect target node UUIDs."""

    name = "virtual_relationship_get_peers"
    type = QueryType.READ

    def __init__(
        self,
        source_id: str,
        virtual_relationship: VirtualRelationshipSchema,
        relationship_schemas: list[RelationshipSchema],
        **kwargs: Any,
    ) -> None:
        self.source_id = source_id
        self.virtual_relationship = virtual_relationship
        self.relationship_schemas = relationship_schemas
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)
        self.params["source_id"] = self.source_id

        segments = self.virtual_relationship.get_path_segments()
        match_pattern, rel_refs = _build_match_pattern(
            segments=segments,
            relationship_schemas=self.relationship_schemas,
            params=self.params,
        )

        kind_filter = ""
        if self.virtual_relationship.peer:
            self.params["target_kind"] = self.virtual_relationship.peer
            kind_filter = "AND $target_kind IN LABELS(target)"

        query = f"""
        MATCH path = {match_pattern}
        WHERE all(r IN [{rel_refs}] WHERE ({branch_filter}))
        {kind_filter}
        AND all(r IN [{rel_refs}] WHERE r.status = "active")
        WITH DISTINCT target
        """

        self.add_to_query(query)
        self.return_labels = ["target.uuid AS peer_id"]
        self.order_by = []

    def get_peer_ids(self) -> list[str]:
        return [str(result.get("peer_id")) for result in self.results]


class VirtualRelationshipCountQuery(Query):
    """Count query for virtual relationship target nodes."""

    name = "virtual_relationship_count"
    type = QueryType.READ
    insert_limit = False

    def __init__(
        self,
        source_id: str,
        virtual_relationship: VirtualRelationshipSchema,
        relationship_schemas: list[RelationshipSchema],
        **kwargs: Any,
    ) -> None:
        self.source_id = source_id
        self.virtual_relationship = virtual_relationship
        self.relationship_schemas = relationship_schemas
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)
        self.params["source_id"] = self.source_id

        segments = self.virtual_relationship.get_path_segments()
        match_pattern, rel_refs = _build_match_pattern(
            segments=segments,
            relationship_schemas=self.relationship_schemas,
            params=self.params,
        )

        kind_filter = ""
        if self.virtual_relationship.peer:
            self.params["target_kind"] = self.virtual_relationship.peer
            kind_filter = "AND $target_kind IN LABELS(target)"

        query = f"""
        MATCH path = {match_pattern}
        WHERE all(r IN [{rel_refs}] WHERE ({branch_filter}))
        {kind_filter}
        AND all(r IN [{rel_refs}] WHERE r.status = "active")
        WITH count(DISTINCT target) AS count
        """

        self.add_to_query(query)
        self.return_labels = ["count"]
