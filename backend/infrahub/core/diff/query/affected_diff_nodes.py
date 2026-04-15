from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class AffectedDiffNodeUUIDsQuery(Query):
    """Get all node UUIDs from the diff graph for metadata updates"""

    name = "affected_diff_node_uuids"
    type = QueryType.READ

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        tracking_id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.at = at
        self.target_branch = target_branch
        self.tracking_id = tracking_id

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.at.to_string(),
            "target_branch": self.target_branch.name,
            "source_branch": self.branch.name,
            "tracking_id": self.tracking_id,
        }
        query = """
MATCH (root:DiffRoot)-[:DIFF_HAS_NODE]->(dn:DiffNode)
WHERE root.diff_branch = $source_branch
AND root.tracking_id = $tracking_id
AND dn.action <> "unchanged"
WITH DISTINCT dn.uuid AS uuid
        """
        self.return_labels = ["uuid"]
        self.add_to_query(query=query)

    def get_node_uuids(self) -> list[str]:
        return [result.get_as_type("uuid", str) for result in self.get_results()]
