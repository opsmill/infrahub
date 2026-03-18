from typing import Any

from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


class EnrichedDiffLinkProposedChangeQuery(Query):
    """Links existing DiffRoot nodes to a ProposedChange by their UUIDs."""

    name = "enriched_diff_link_proposed_change"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        diff_uuids: list[str],
        proposed_change_id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.diff_uuids = diff_uuids
        self.proposed_change_id = proposed_change_id

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "diff_uuids": self.diff_uuids,
            "proposed_change_id": self.proposed_change_id,
        }
        query = """
MATCH (pc:Node {uuid: $proposed_change_id})
MATCH (diff_root:DiffRoot)
WHERE diff_root.uuid IN $diff_uuids
MERGE (diff_root)-[:DIFF_FOR_PROPOSED_CHANGE]->(pc)
        """
        self.add_to_query(query)
