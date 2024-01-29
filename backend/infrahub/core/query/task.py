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
