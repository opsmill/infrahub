from __future__ import annotations

from typing import TYPE_CHECKING, Any, List

from infrahub.core.constants import InfrahubKind
from infrahub.core.query import QueryType

from .standard_node import StandardNodeQuery

if TYPE_CHECKING:
    from infrahub.core.task import Task
    from infrahub.database import InfrahubDatabase


class TaskNodeCreateQuery(StandardNodeQuery):
    name: str = "task_create"
    node: Task

    type: QueryType = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        node_type = self.node.get_type()
        self.params["node_prop"] = self.node.to_db()
        self.params["created_at"] = self.params["node_prop"].pop("created_at")
        relationships = []

        if self.node.account_id:
            query = """
            MATCH (a:%(account_kind)s {uuid: $account_id})
            """ % {"account_kind": InfrahubKind.ACCOUNT}
            self.add_to_query(query=query)
            self.params["account_id"] = self.node.account_id
            relationships.append(
                """
                MERGE (n)-[:CREATED_BY]->(a)
                """
            )

        if self.node.related_node:
            query = """
            MATCH (i:%(node_kind)s {uuid: $related_id})
            """ % {"node_kind": self.node.related_node.get_kind()}
            self.add_to_query(query=query)
            self.params["related_id"] = self.node.related_node.get_id()
            relationships.append(
                """
                MERGE (n)-[:IMPACTS]->(i)
                """
            )

        query = """
        MATCH (root:Root)
        MERGE (n:%(node_type)s {uuid: $node_prop.uuid})
        ON CREATE SET n.created_at = $created_at, n += $node_prop
        ON MATCH SET n += $node_prop
        MERGE (n)-[r:IS_PART_OF]->(root)
        """ % {"node_type": node_type}
        self.add_to_query(query=query)

        for relationship in relationships:
            self.add_to_query(query=relationship)
        self.return_labels = ["n"]


class TaskNodeQuery(StandardNodeQuery):
    name: str = "task_query"

    type: QueryType = QueryType.READ
    insert_return: bool = False

    def __init__(
        self,
        related_nodes: List[str],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.related_nodes = related_nodes
        self.params["related_nodes"] = self.related_nodes

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        self.add_to_query(query="MATCH (n:Task)-[:IMPACTS]->(rn:Node)")
        if self.related_nodes:
            self.add_to_query(query="WHERE rn.uuid IN $related_nodes")

        if self.limit:
            # All regular queries will include a limit this is to avoid ordering the count query
            self.add_to_query(query="RETURN n,rn")
            self.add_to_query(query="ORDER BY n.created_at DESC")

            self.return_labels = [
                "n",
                "rn",
            ]


class TaskNodeQueryWithLogs(TaskNodeQuery):
    name: str = "task_query_with_logs"
    insert_return: bool = False

    type: QueryType = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        self.add_to_query(query="MATCH (n:Task)-[:IMPACTS]->(rn:Node)")
        if self.related_nodes:
            self.add_to_query(query="WHERE rn.uuid IN $related_nodes")

        query = """
        OPTIONAL MATCH (n)<-[r:RELATES_TO]-(l:TaskLog)
        WITH n, rn, COLLECT(l) as logs
        ORDER BY n.created_at DESC
        RETURN n, logs, rn
        """

        self.add_to_query(query=query)

        self.return_labels = [
            "n",
            "logs",
            "rn",
        ]
