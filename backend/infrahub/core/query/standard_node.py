from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType
from infrahub.exceptions import InitializationError

if TYPE_CHECKING:
    from uuid import UUID

    from infrahub.core.node.standard import StandardNode
    from infrahub.database import InfrahubDatabase


class StandardNodeQuery(Query):
    def __init__(
        self,
        node: StandardNode | None = None,
        node_id: UUID | None = None,
        node_db_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._node = node
        self.node_id = node_id
        self.node_db_id = node_db_id

        if not self.node_id and self._node:
            self.node_id = self.node.uuid

        if not self.node_db_id and self._node:
            self.node_db_id = self.node.id

        super().__init__(**kwargs)

    @property
    def node(self) -> StandardNode:
        if self._node:
            return self._node

        raise InitializationError("The query is not initialized with a node")


class RootNodeCreateQuery(StandardNodeQuery):
    name = "standard_node_create"
    type = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        node_type = self.node.get_type()
        self.params["node_prop"] = self.node.to_db()

        query = """
        CREATE (n:%s $node_prop)
        """ % (node_type)

        self.add_to_query(query=query)
        self.return_labels = ["n"]


class StandardNodeCreateQuery(StandardNodeQuery):
    name = "standard_node_create"
    type = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        node_type = self.node.get_type()
        self.params["node_prop"] = self.node.to_db()

        query = """
        MATCH (root:Root)
        CREATE (n:%s $node_prop)-[r:IS_PART_OF]->(root)
        """ % (node_type)

        self.add_to_query(query=query)
        self.return_labels = ["n"]


class StandardNodeUpdateQuery(StandardNodeQuery):
    name = "standard_node_update"
    type = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.node.get_type()
        self.params["node_prop"] = self.node.to_db()
        self.params["node_prop"]["uuid"] = str(self.node.uuid)
        self.params["uuid"] = str(self.node.uuid)

        query = """
        MATCH (n:%s { uuid: $uuid })
        SET n = $node_prop
        """ % (self.node.get_type(),)

        self.add_to_query(query=query)
        self.return_labels = ["n"]


class StandardNodeDeleteQuery(StandardNodeQuery):
    name = "standard_node_delete"
    insert_return = False
    type = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        MATCH (n:%s { uuid: $uuid })
        DETACH DELETE (n)
        """ % (self.node.get_type())

        self.params["uuid"] = str(self.node_id)
        self.add_to_query(query)


class StandardNodeGetItemQuery(Query):
    name = "standard_node_get"
    type = QueryType.READ

    def __init__(self, node_id: str, node_type: str, **kwargs: Any) -> None:
        self.node_id = node_id
        self.node_type = node_type

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
            MATCH (n:%(node_type)s)
            WHERE %(id_func)s(n) = $node_id OR n.uuid = $node_id
            """ % {"node_type": self.node_type, "id_func": db.get_id_function_name()}

        self.params["node_id"] = self.node_id
        self.add_to_query(query)

        self.return_labels = ["n"]


class StandardNodeGetListQuery(Query):
    name = "standard_node_list"
    type = QueryType.READ

    def __init__(
        self, node_class: StandardNode, ids: list[str] | None = None, node_name: str | None = None, **kwargs: Any
    ) -> None:
        self.ids = ids
        self.node_name = node_name
        self.node_class = node_class

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        filters = []
        if self.ids:
            filters.append("n.uuid in $ids_value")
            self.params["ids_value"] = self.ids
        if self.node_name:
            filters.append("n.name = $name")
            self.params["name"] = self.node_name

        where = ""
        if filters:
            where = f"WHERE {' AND '.join(filters)}"

        query = """
        MATCH (n:%s)
        %s
        """ % (
            self.node_class.get_type(),
            where,
        )

        self.add_to_query(query)

        self.return_labels = ["n"]
        self.order_by = [f"{db.get_id_function_name()}(n)"]
