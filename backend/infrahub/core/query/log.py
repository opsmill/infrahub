from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import TaskConclusion
from infrahub.core.query import QueryType
from infrahub.core.timestamp import current_timestamp

from .standard_node import StandardNodeQuery

if TYPE_CHECKING:
    from infrahub.core.log import Log
    from infrahub.database import InfrahubDatabase


class LogNodeCreateQuery(StandardNodeQuery):
    name: str = "log_create"
    node: Log

    type: QueryType = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        node_type = self.node.get_type()
        self.params["node_prop"] = self.node.to_db()
        self.params["task_id"] = self.node.task_id

        # If the request to create the Log arrives earlier that that of the creation of the Task
        # we want the relationship to be setup regardless so that it's in place for when the
        # Task gets propperly created.
        query = """
        MATCH (root:Root)
        CREATE (n:%(node_type)s $node_prop)-[r:IS_PART_OF]->(root)
        MERGE (t:Task {uuid: $task_id})
        ON CREATE SET t.created_at = "%(timestamp)s", t.updated_at = "%(timestamp)s", t.conclusion = "%(conclusion)s"
        CREATE (n)-[:RELATES_TO]->(t)
        """ % {"node_type": node_type, "timestamp": current_timestamp(), "conclusion": TaskConclusion.UNKNOWN.value}
        self.add_to_query(query=query)
        self.return_labels = ["n"]


class LogNodeQuery(StandardNodeQuery):
    name: str = "log_query"

    type: QueryType = QueryType.READ
    page_size: int
    has_next: bool = False
    next_cursor: str = ""
    insert_return: bool = False

    def __init__(
        self,
        page_size: int,
        cursor: str,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.page_size = page_size
        self.cursor = cursor

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        self.page_size = kwargs.pop("page_size")
        self.cursor = kwargs.pop("cursor")
        cursor_filter = ""
        if self.cursor:
            self.params["cursor"] = self.cursor
            cursor_filter = "WHERE n.timestamp <= $cursor"
        query = """
        MATCH (n:Log)-[:RELATES_TO]->(t:Task)-[:IMPACTS]->(rn:Node)
        %(cursor_filter)s
        RETURN n, rn, t
        ORDER BY n.timestamp desc
        LIMIT %(limit)s
        """ % {"cursor_filter": cursor_filter, "limit": self.page_size + 1}
        self.add_to_query(query=query)

        self.return_labels = [
            "n",
            "rn",
            "t",
        ]

    async def execute(self, db: InfrahubDatabase, enforce_limit: bool = False) -> LogNodeQuery:
        await super().execute(db=db, enforce_limit=False)
        if len(self.results) > self.page_size:
            self.has_next = True
            self.next_cursor = self.results[-1:][0].get("n").get("timestamp")
            self.results = self.results[: self.page_size]
        return self
