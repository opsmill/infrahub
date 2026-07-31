from collections.abc import Generator
from typing import Any

from infrahub.core.constants import DiffAction
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase

from ..model.path import NodeDiffFieldSummary, TrackingId


class EnrichedDiffNodeFieldSummaryQuery(Query):
    """Get the names of all altered attributes and relationships for one page of changed nodes.

    Pagination is over the changed nodes, strictly ordered, with each row carrying every altered
    field name of one node; aggregating the fields of every node in one transaction does not scale
    with large diffs.
    """

    name = "enriched_diff_node_field_summary"
    type = QueryType.READ

    def __init__(
        self,
        diff_branch_name: str,
        node_offset: int,
        node_limit: int,
        tracking_id: TrackingId | None = None,
        diff_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.diff_branch_name = diff_branch_name
        self.node_offset = node_offset
        self.node_limit = node_limit
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
            "node_offset": self.node_offset,
            "node_limit": self.node_limit,
        }
        query = """
        MATCH (diff_root:DiffRoot)
        WHERE (diff_root.is_merged IS NULL OR diff_root.is_merged <> TRUE)
        AND diff_root.diff_branch = $diff_branch
        AND (diff_root.tracking_id = $tracking_id OR $tracking_id IS NULL)
        AND (diff_root.uuid = $diff_id OR $diff_id IS NULL)
        OPTIONAL MATCH (diff_root)-[:DIFF_HAS_NODE]->(n:DiffNode)
        WHERE n.action <> $unchanged_str
        WITH n
        ORDER BY n.uuid, elementId(n)
        SKIP $node_offset
        LIMIT $node_limit
        CALL (n) {
            OPTIONAL MATCH (n)-[:DIFF_HAS_ATTRIBUTE]->(a:DiffAttribute)
            WHERE a.action <> $unchanged_str
            RETURN collect(DISTINCT a.name) AS attr_names
        }
        CALL (n) {
            OPTIONAL MATCH (n)-[:DIFF_HAS_RELATIONSHIP]->(r:DiffRelationship)
            WHERE r.action <> $unchanged_str
            RETURN collect(DISTINCT r.name) AS rel_names
        }
        """
        self.add_to_query(query=query)
        self.return_labels = ["n.kind AS kind", "n.uuid AS node_uuid", "attr_names", "rel_names"]

    def get_node_field_rows(self) -> Generator[NodeDiffFieldSummary, None, None]:
        """Yield a single-node field summary for each changed node in this page.

        A node whose fields are all unchanged still yields a summary (with empty field maps) so the
        caller can count the nodes consumed from this page. A diff root with no changed nodes at all
        produces one node-less row instead; it is skipped here, which is safe for the caller's
        consumed-node count because null nodes sort after every real node.
        """
        for result in self.get_results():
            kind = result.get_as_str("kind")
            node_uuid = result.get_as_str("node_uuid")
            if not kind or not node_uuid:
                continue
            summary = NodeDiffFieldSummary(kind=kind)
            for attr_name in result.get_as_type(label="attr_names", return_type=list[str]):
                summary.add_attribute_node_uuid(name=attr_name, node_uuid=node_uuid)
            for rel_name in result.get_as_type(label="rel_names", return_type=list[str]):
                summary.add_relationship_node_uuid(name=rel_name, node_uuid=node_uuid)
            yield summary
