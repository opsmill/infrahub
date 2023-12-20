from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.node.standard import StandardNode
    from infrahub.database import InfrahubDatabase


class StandardNodeQuery(Query):
    def __init__(
        self,
        node: StandardNode = None,
        node_id: Optional[str] = None,
        node_db_id: Optional[int] = None,
        *args,
        **kwargs,
    ):
        self.node = node
        self.node_id = node_id
        self.node_db_id = node_db_id

        if not self.node_id and self.node:
            self.node_id = self.node.uuid

        if not self.node_db_id and self.node:
            self.node_db_id = self.node.id

        super().__init__(*args, **kwargs)


class StandardNodeCreateQuery(StandardNodeQuery):
    name: str = "standard_node_create"

    type: QueryType = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        node_type = self.node.get_type()
        self.params["node_prop"] = self.node.to_db()

        query = """
        CREATE (n:%s $node_prop)
        """ % (node_type)

        self.add_to_query(query=query)
        self.return_labels = ["n"]


class StandardNodeUpdateQuery(StandardNodeQuery):
    name: str = "standard_node_update"

    type: QueryType = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
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
    name: str = "standard_node_delete"
    insert_return: bool = False

    type: QueryType = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        query = """
        MATCH (n:%s { uuid: $uuid })
        DETACH DELETE (n)
        """ % (self.node.get_type())

        self.params["uuid"] = str(self.node_id)
        self.add_to_query(query)


class StandardNodeGetItemQuery(Query):
    name: str = "standard_node_get"

    type: QueryType = QueryType.WRITE

    def __init__(
        self,
        node_id: str,
        node_type: str,
        *args,
        **kwargs,
    ):
        self.node_id = node_id
        self.node_type = node_type

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        query = (
            """
            MATCH (n:%s)
            WHERE ID(n) = $node_id OR n.uuid = $node_id
            """
            % self.node_type
        )

        self.params["node_id"] = self.node_id
        self.add_to_query(query)

        self.return_labels = ["n"]


class StandardNodeGetListQuery(Query):
    name: str = "standard_node_list"

    type: QueryType = QueryType.WRITE

    def __init__(
        self,
        node_class: StandardNode,
        ids: Optional[List[str]] = None,
        name: Optional[str] = None,
        *args,
        **kwargs,
    ):
        self.ids = ids
        self.name = name
        self.node_class = node_class

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        filters = []
        if self.ids:
            filters.append("n.uuid in $ids_value")
            self.params["ids_value"] = self.ids
        if self.name:
            filters.append("n.name = $name")
            self.params["name"] = self.name

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
        self.order_by = ["ID(n)"]
