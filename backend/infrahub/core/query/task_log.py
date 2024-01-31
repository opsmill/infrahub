from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import TaskConclusion
from infrahub.core.query import QueryType
from infrahub.core.timestamp import current_timestamp

from .standard_node import StandardNodeQuery

if TYPE_CHECKING:
    from infrahub.core.task_log import TaskLog
    from infrahub.database import InfrahubDatabase


class TaskLogNodeCreateQuery(StandardNodeQuery):
    name: str = "log_create"
    node: TaskLog

    type: QueryType = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        node_type = self.node.get_type()
        self.params["node_prop"] = self.node.to_db()
        self.params["task_id"] = self.node.task_id

        # If the request to create the Log arrives earlier that that of the creation of the Task
        # we want the relationship to be setup regardless so that it's in place for when the
        # Task gets propperly created.
        query = """
        CREATE (n:%(node_type)s $node_prop)
        MERGE (t:Task {uuid: $task_id})
        ON CREATE SET t.created_at = "%(timestamp)s", t.updated_at = "%(timestamp)s", t.conclusion = "%(conclusion)s"
        CREATE (n)-[:RELATES_TO]->(t)
        """ % {"node_type": node_type, "timestamp": current_timestamp(), "conclusion": TaskConclusion.UNKNOWN.value}
        self.add_to_query(query=query)
        self.return_labels = ["n"]
