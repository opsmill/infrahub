import uuid
from typing import List, Optional, TypeVar
from uuid import UUID

from neo4j import AsyncSession
from pydantic import BaseModel

from infrahub.core.query import Query, QueryType
from infrahub.database import execute_read_query_async, execute_write_query_async
from infrahub.exceptions import QueryError

SelfNode = TypeVar("SelfNode", bound="StandardNode")

# pylint: disable=redefined-builtin


class StandardNode(BaseModel):
    id: Optional[str]
    uuid: Optional[UUID]

    # owner: Optional[str]

    _exclude_attrs: List[str] = ["id", "uuid", "owner"]

    @classmethod
    def get_type(cls) -> str:
        return cls.__name__

    async def to_graphql(self, fields: dict) -> dict:
        response = {"id": self.uuid}

        for field_name in fields.keys():
            if field_name in ["id"]:
                continue
            if field_name == "__typename":
                response[field_name] = self.get_type()
                continue
            field = getattr(self, field_name)
            if field is None:
                response[field_name] = None
                continue
            response[field_name] = field

        return response

    async def save(self, session: AsyncSession):
        """Create or Update the Node in the database."""

        if self.id:
            return await self._update(session=session)

        return await self._create(session=session)

    async def delete(self, session: AsyncSession):
        """Delete the Node in the database."""

        query = await StandardNodeDeleteQuery.init(
            session=session, node_type=self.get_type(), identifier=str(self.uuid)
        )
        await query.execute(session=session)

    async def refresh(self, session: AsyncSession):
        """Pull the latest state of the object from the database."""

        # Might need ot check how to manage the default value
        raw_attrs = self._get_item_raw(self.id, session=session)
        for item in raw_attrs:
            if item[1] != getattr(self, item[0]):
                setattr(self, item[0], item[1])

        return True

    async def _create(self, session: AsyncSession):
        """Create a new node in the database."""

        node_type = self.get_type()

        attrs = []
        params = {"uuid": str(uuid.uuid4())}
        for attr_name in self.__fields__:
            if attr_name in self._exclude_attrs:
                continue
            attrs.append(f"{attr_name}: ${attr_name}")
            params[attr_name] = getattr(self, attr_name)

        if attrs:
            query = """
            CREATE (n:%s { uuid: $uuid, %s })
            RETURN n
            """ % (
                node_type,
                ", ".join(attrs),
            )
        else:
            query = (
                """
            CREATE (n:%s { uuid: $uuid })
            RETURN n
            """
                % node_type
            )

        results = await execute_write_query_async(session=session, query=query, params=params)
        if not results:
            raise QueryError(query=query, params=params, message="Unexpected error, unable to create the new node.")

        node = results[0][0]

        self.id = node.element_id
        self.uuid = node["uuid"]

        return True

    async def _update(self, session: AsyncSession):
        """Update the node in the database if needed."""

        attrs = []
        for attr_name in self.__fields__:
            if attr_name in self._exclude_attrs and attr_name != "uuid":
                continue
            attrs.append(f"{attr_name}: '{getattr(self, attr_name)}'")

        query = """
        MATCH (n:%s { uuid: $uuid })
        SET n = { %s }
        RETURN n
        """ % (
            self.get_type(),
            ",".join(attrs),
        )

        params = {"uuid": str(self.uuid)}

        results = await execute_write_query_async(session=session, query=query, params=params)

        if not results:
            raise QueryError(
                query=query,
                params=params,
                message=f"Unexpected error, unable to update the node {self.id} / {self.uuid}.",
            )
        return True

    @classmethod
    async def get(cls, id: str, session: AsyncSession):
        """Get a node from the database identied by its ID."""

        node = await cls._get_item_raw(id=id, session=session)
        if node:
            return cls._convert_node_to_obj(node)

        return None

    @classmethod
    async def _get_item_raw(cls, id: str, session: AsyncSession):
        query = (
            """
        MATCH (n:%s)
        WHERE ID(n) = $node_id OR n.uuid = $node_id
        RETURN n
        """
            % cls.get_type()
        )

        params = {"node_id": id}

        results = await execute_read_query_async(session=session, query=query, params=params, name="standard_get")
        if len(results):
            return results[0].values()[0]

    @classmethod
    def _convert_node_to_obj(cls, node):
        """Convert a Neo4j Node to a Infrahub StandardNode

        Args:
            node (neo4j.graph.Node): Neo4j Node object

        Returns:
            StandardNode: Proper StandardNode object
        """

        attrs = dict(node)
        attrs["id"] = node.element_id
        for key, value in attrs.items():
            if value == "None":
                attrs[key] = None

        return cls(**attrs)

    @classmethod
    async def get_list(cls, session: AsyncSession, limit: int = 1000, **kwargs) -> List[SelfNode]:
        params = {"limit": limit}

        filters = []
        if ids := kwargs.get("ids"):
            filters.append("n.uuid in $ids_value")
            params["ids_value"] = ids
        if name_filter := kwargs.get("name"):
            filters.append("n.name = $name")
            params["name"] = name_filter

        where = ""
        if filters:
            where = f"WHERE {' AND '.join(filters)}"

        query = f"""
        MATCH (n:{cls.get_type()})
        {where}
        RETURN n
        ORDER BY ID(n)
        LIMIT $limit
        """

        results = await execute_read_query_async(session=session, query=query, params=params, name="standard_get_list")
        return [cls._convert_node_to_obj(node.values()[0]) for node in results]


class StandardNodeDeleteQuery(Query):
    name: str = "standard_node_delete"
    insert_return: bool = False

    type: QueryType = QueryType.WRITE

    def __init__(self, node_type: str, identifier: str, *args, **kwargs):
        self.node_type = node_type
        self.uuid = identifier
        super().__init__(*args, **kwargs)

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        query = """
        MATCH (n:%s {uuid: $uuid})
        DETACH DELETE (n)
        """ % (
            self.node_type
        )

        self.params["uuid"] = self.uuid
        self.add_to_query(query)
