from typing import Any

from infrahub.core.constants import DiffAction
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase

from ..model.path import NodeDiffFieldSummary, TrackingId


class EnrichedDiffNodeFieldSummaryQuery(Query):
    """
    Get node kind and names of all altered attributes and relationships for each kind
    """

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
        WITH DISTINCT n.kind AS kind
        CALL {
            WITH kind
            OPTIONAL MATCH (n:DiffNode {kind: kind})-[:DIFF_HAS_ATTRIBUTE]->(a:DiffAttribute)
            WHERE n.action <> $unchanged_str
            AND a.action <> $unchanged_str
            WITH DISTINCT a.name AS attr_name
            RETURN collect(attr_name) AS attr_names
        }
        WITH kind, attr_names
        CALL {
            WITH kind
            OPTIONAL MATCH (n:DiffNode {kind: kind})-[:DIFF_HAS_RELATIONSHIP]->(r:DiffRelationship)
            WHERE n.action <> $unchanged_str
            AND r.action <> $unchanged_str
            WITH DISTINCT r.name AS rel_name
            RETURN collect(rel_name) AS rel_names
        }
        """
        self.add_to_query(query=query)
        self.return_labels = ["kind", "attr_names", "rel_names"]

    async def get_field_summaries(self) -> list[NodeDiffFieldSummary]:
        field_summaries = []
        for result in self.get_results():
            kind = result.get_as_type(label="kind", return_type=str)
            attr_names = result.get_as_type(label="attr_names", return_type=list[str])
            rel_names = result.get_as_type(label="rel_names", return_type=list[str])
            if attr_names or rel_names:
                field_summaries.append(
                    NodeDiffFieldSummary(kind=kind, attribute_names=set(attr_names), relationship_names=set(rel_names))
                )
        return field_summaries
