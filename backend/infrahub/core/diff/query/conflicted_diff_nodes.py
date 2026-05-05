from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class ConflictedDiffNodesQuery(Query):
    """Query the diff for node UUIDs that include conflicts at any level"""

    name = "conflicted_diff_nodes"
    type = QueryType.READ

    def __init__(
        self,
        diff_branch_name: str,
        tracking_id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.diff_branch_name = diff_branch_name
        self.tracking_id = tracking_id

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "diff_branch_name": self.diff_branch_name,
            "tracking_id": self.tracking_id,
        }
        query = """
MATCH (root:DiffRoot)
WHERE root.tracking_id = $tracking_id
AND root.diff_branch = $diff_branch_name
MATCH (root)-[:DIFF_HAS_NODE]->(dn:DiffNode)
WHERE dn.contains_conflict = TRUE
WITH DISTINCT dn.uuid AS uuid
        """
        self.return_labels = ["uuid"]
        self.add_to_query(query=query)

    def get_conflict_uuids(self) -> set[str]:
        return {result.get_as_type("uuid", str) for result in self.get_results()}
