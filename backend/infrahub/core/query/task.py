from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        node_type = self.node.get_type()
        self.params["node_prop"] = self.node.to_db()
        self.params["related_id"] = self.node.related.get_id()

        created_by = ""
        if self.node.account_id:
            query = """
            MATCH (a:%(account_kind)s {uuid: $account_id})
            """ % {"account_kind": InfrahubKind.ACCOUNT}
            self.add_to_query(query=query)
            self.params["account_id"] = self.node.account_id
            created_by = "CREATE (n)-[:CREATED_BY]->(a)"

        query = """
        MATCH (root:Root)
        MATCH (i:%(related_node_kind)s {uuid: $related_id})
        CREATE (n:%(node_type)s $node_prop)-[r:IS_PART_OF]->(root)
        CREATE (n)-[:IMPACTS]->(i)
        %(created_by)s
        """ % {"created_by": created_by, "node_type": node_type, "related_node_kind": self.node.related.get_kind()}
        self.add_to_query(query=query)

        self.return_labels = ["n"]


class TaskNodeQuery(StandardNodeQuery):
    name: str = "task_query"

    type: QueryType = QueryType.READ

    def __init__(self, ids: list[str], related_nodes: list[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.ids = ids
        self.related_nodes = related_nodes
        self.params["related_nodes"] = self.related_nodes
        self.params["ids"] = self.ids

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.add_to_query(query="MATCH (n:Task)-[:IMPACTS]->(rn:Node)")
        if self.ids:
            self.add_to_query(query="WHERE n.uuid in $ids")
        if self.related_nodes:
            self.add_to_query(query="WHERE rn.uuid IN $related_nodes")

        self.order_by = ["n.created_at DESC"]
        self.return_labels = [
            "n",
            "rn",
        ]


class TaskNodeQueryWithLogs(TaskNodeQuery):
    name: str = "task_query_with_logs"

    type: QueryType = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.add_to_query(query="MATCH (n:Task)-[:IMPACTS]->(rn:Node)")
        if self.ids:
            self.add_to_query(query="WHERE n.uuid in $ids")
        if self.related_nodes:
            self.add_to_query(query="WHERE rn.uuid IN $related_nodes")

        query = """
        OPTIONAL MATCH (n)<-[r:RELATES_TO]-(l:TaskLog)
        WITH n, rn, COLLECT(l) as logs
        """

        self.add_to_query(query=query)
        self.order_by = ["n.created_at DESC"]

        self.return_labels = [
            "n",
            "logs",
            "rn",
        ]
