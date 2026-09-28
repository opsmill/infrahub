from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class AffectedDiffNodeUUIDsQuery(Query):
    """Get node UUIDs from the diff graph, optionally filtered by diff action."""

    name = "affected_diff_node_uuids"
    type = QueryType.READ

    def __init__(
        self,
        diff_branch_name: str,
        tracking_id: str,
        include_actions: list[str] | None = None,
        exclude_actions: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.diff_branch_name = diff_branch_name
        self.tracking_id = tracking_id
        self.include_actions = include_actions
        self.exclude_actions = exclude_actions

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "diff_branch_name": self.diff_branch_name,
            "tracking_id": self.tracking_id,
            "include_actions": self.include_actions,
            "exclude_actions": self.exclude_actions,
        }
        query = """
MATCH (root:DiffRoot)-[:DIFF_HAS_NODE]->(dn:DiffNode)
WHERE root.diff_branch = $diff_branch_name
AND root.tracking_id = $tracking_id
AND ($include_actions IS NULL OR dn.action IN $include_actions)
AND ($exclude_actions IS NULL OR NOT dn.action IN $exclude_actions)
WITH DISTINCT dn.uuid AS uuid
        """
        self.return_labels = ["uuid"]
        self.add_to_query(query=query)

    def get_node_uuids(self) -> list[str]:
        return [result.get_as_type("uuid", str) for result in self.get_results()]
