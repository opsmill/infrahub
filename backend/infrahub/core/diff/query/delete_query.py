from typing import Any

from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


class EnrichedDiffDeleteQuery(Query):
    name = "enriched_diff_delete"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, enriched_diff_root_uuids: list[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.enriched_diff_root_uuids = enriched_diff_root_uuids

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {"diff_root_uuids": self.enriched_diff_root_uuids}
        query = """
        MATCH (d_root:DiffRoot)
        WHERE d_root.uuid IN $diff_root_uuids
        OPTIONAL MATCH (d_root)-[*]->(diff_thing)
        DETACH DELETE diff_thing
        DETACH DELETE d_root
        """
        self.add_to_query(query=query)
