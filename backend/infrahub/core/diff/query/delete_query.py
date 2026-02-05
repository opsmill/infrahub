from typing import Any

from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


class EnrichedDiffDeleteQuery(Query):
    name = "enriched_diff_delete"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        enriched_diff_root_uuids: list[str] | None = None,
        include_frozen: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.enriched_diff_root_uuids = enriched_diff_root_uuids
        self.include_frozen = include_frozen

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        diff_filters = []
        self.params = {}
        if self.enriched_diff_root_uuids:
            self.params["diff_root_uuids"] = self.enriched_diff_root_uuids
            diff_filters.append("d_root.uuid IN $diff_root_uuids")
        if not self.include_frozen:
            diff_filters.append("(d_root.is_frozen IS NULL OR d_root.is_frozen <> TRUE)")

        diff_filter = ""
        if diff_filters:
            diff_filter = "WHERE " + " AND ".join(diff_filters)

        query = """
MATCH (d_root:DiffRoot)
%(diff_filter)s
OPTIONAL MATCH (d_root)-[*]->(diff_thing:DiffRoot|DiffNode|DiffAttribute|DiffRelationship|DiffRelationshipElement|DiffProperty|DiffConflict)
WITH DISTINCT d_root, diff_thing
ORDER BY elementId(diff_thing)
CALL (diff_thing) {
    DETACH DELETE diff_thing
} IN TRANSACTIONS
DETACH DELETE d_root
        """ % {"diff_filter": diff_filter}
        self.add_to_query(query=query)
