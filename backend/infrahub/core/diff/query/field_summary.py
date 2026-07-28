from dataclasses import dataclass
from typing import Any

from infrahub.core.constants import DiffAction
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase

from ..model.path import NodeDiffFieldSummary, TrackingId


@dataclass
class FieldNodeUuidsRow:
    """One changed field of a kind and the uuids of the nodes that changed it, as projected by the query."""

    name: str
    node_uuids: list[str]


class EnrichedDiffNodeFieldSummaryQuery(Query):
    """Get node kind and names of all altered attributes and relationships for each kind."""

    name = "enriched_diff_node_field_summary"
    type = QueryType.READ

    def __init__(
        self,
        diff_branch_name: str,
        tracking_id: TrackingId | None = None,
        diff_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.diff_branch_name = diff_branch_name
        self.tracking_id = tracking_id
        self.diff_id = diff_id

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        if self.tracking_id is None and self.diff_id is None:
            raise RuntimeError("Either tacking_id or diff_id is required")
        self.params = {
            "unchanged_str": DiffAction.UNCHANGED.value,
            "diff_branch": self.diff_branch_name,
            "tracking_id": self.tracking_id.serialize() if self.tracking_id else None,
            "diff_id": self.diff_id,
        }
        query = """
        MATCH (diff_root:DiffRoot)
        WHERE (diff_root.is_merged IS NULL OR diff_root.is_merged <> TRUE)
        AND diff_root.diff_branch = $diff_branch
        AND (diff_root.tracking_id = $tracking_id OR $tracking_id IS NULL)
        AND (diff_root.uuid = $diff_id OR $diff_id IS NULL)
        OPTIONAL MATCH (diff_root)-[:DIFF_HAS_NODE]->(n:DiffNode)
        WHERE n.action <> $unchanged_str
        WITH DISTINCT diff_root, n.kind AS kind
        CALL (diff_root, kind) {
            OPTIONAL MATCH (diff_root)-[:DIFF_HAS_NODE]->(n:DiffNode {kind: kind})-[:DIFF_HAS_ATTRIBUTE]->(a:DiffAttribute)
            WHERE n.action <> $unchanged_str
            AND a.action <> $unchanged_str
            WITH a.name AS attr_name, collect(DISTINCT n.uuid) AS attr_node_uuids
            WHERE attr_name IS NOT NULL
            RETURN collect({name: attr_name, node_uuids: attr_node_uuids}) AS attr_name_uuids
        }
<<<<<<< HEAD
        WITH kind, attr_name_uuids
        CALL (kind) {
            OPTIONAL MATCH (n:DiffNode {kind: kind})-[:DIFF_HAS_RELATIONSHIP]->(r:DiffRelationship)
=======
        WITH diff_root, kind, attr_names
        CALL (diff_root, kind) {
            OPTIONAL MATCH (diff_root)-[:DIFF_HAS_NODE]->(n:DiffNode {kind: kind})-[:DIFF_HAS_RELATIONSHIP]->(r:DiffRelationship)
>>>>>>> origin/stable
            WHERE n.action <> $unchanged_str
            AND r.action <> $unchanged_str
            WITH r.name AS rel_name, collect(DISTINCT n.uuid) AS rel_node_uuids
            WHERE rel_name IS NOT NULL
            RETURN collect({name: rel_name, node_uuids: rel_node_uuids}) AS rel_name_uuids
        }
        """
        self.add_to_query(query=query)
        self.order_by = ["kind"]
        self.return_labels = ["kind", "attr_name_uuids", "rel_name_uuids"]

    async def get_field_summaries(self) -> list[NodeDiffFieldSummary]:
        field_summaries = []
        for result in self.get_results():
            kind = result.get_as_type(label="kind", return_type=str)
            attribute_node_uuids = self._to_field_uuids(
                result.get_as_list_of_type(label="attr_name_uuids", return_type=FieldNodeUuidsRow)
            )
            relationship_node_uuids = self._to_field_uuids(
                result.get_as_list_of_type(label="rel_name_uuids", return_type=FieldNodeUuidsRow)
            )
            if attribute_node_uuids or relationship_node_uuids:
                field_summaries.append(
                    NodeDiffFieldSummary(
                        kind=kind,
                        attribute_node_uuids=attribute_node_uuids,
                        relationship_node_uuids=relationship_node_uuids,
                    )
                )
        return field_summaries

    def _to_field_uuids(self, rows: list[FieldNodeUuidsRow]) -> dict[str, set[str]]:
        return {row.name: set(row.node_uuids) for row in rows}
