from typing import Any

from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


class DeleteAfterTimeQuery(Query):
    name: str = "delete_after_time"
    insert_return: bool = False
    type: QueryType = QueryType.WRITE

    def __init__(self, timestamp: Timestamp, **kwargs: Any):
        self.timestamp = timestamp
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params = {"timestamp": self.timestamp.to_string()}
        query = """
// ---------------------
// Reset edges with to time after timestamp
// ---------------------
CALL {
    OPTIONAL MATCH (p)-[r]-(q)
    WHERE r.to > $timestamp
    SET r.to = NULL
}
// ---------------------
// Delete edges with from time after timestamp timestamp
// ---------------------
CALL {
    OPTIONAL MATCH (p)-[r]->(q)
    WHERE r.from > $timestamp
    DELETE r
    WITH p, q
    UNWIND [p, q] AS maybe_orphan
    WITH maybe_orphan
    WHERE NOT exists((maybe_orphan)--())
    DELETE maybe_orphan
}
"""
        self.add_to_query(query)

        # if config.SETTINGS.database.db_type == config.DatabaseType.MEMGRAPH:
        #     query = """
        #     MATCH p = (s)-[r]-(d)
        #     WHERE r.branch = $branch_name
        #     DELETE r
        #     """
        # else:
        #     query = """
        #     MATCH p = (s)-[r]-(d)
        #     WHERE r.branch = $branch_name
        #     DELETE r
        #     WITH *
        #     UNWIND nodes(p) AS n
        #     MATCH (n)
        #     WHERE NOT exists((n)--())
        #     DELETE n
        #     """
        # self.params["branch_name"] = self.branch_name
        # self.add_to_query(query)
