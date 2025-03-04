from typing import Any

from infrahub import config
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

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {"timestamp": self.timestamp.to_string()}
        query_1 = """
        // ---------------------
        // Reset edges with to time after timestamp
        // ---------------------
        CALL {
            OPTIONAL MATCH (p)-[r]-(q)
            WHERE r.to > $timestamp
            SET r.to = NULL
        }
        """
        self.add_to_query(query_1)
        if config.SETTINGS.database.db_type is config.DatabaseType.NEO4J:
            query_2 = """
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
        else:
            query_2 = """
            // ---------------------
            // Delete edges with from time after timestamp timestamp
            // ---------------------
            CALL {
                OPTIONAL MATCH (p)-[r]->(q)
                WHERE r.from > $timestamp
                DELETE r
            }
            """
        self.add_to_query(query_2)
