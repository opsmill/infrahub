import uuid
from uuid import UUID
from typing import List, Optional, TypeVar

from pydantic import BaseModel

from neo4j import AsyncSession

from infrahub.database import execute_read_query_async, execute_write_query_async

SelfNode = TypeVar("SelfNode", bound="StandardNode")


class StandardNode(BaseModel):

    id: Optional[str]
    uuid: Optional[UUID]

    # owner: Optional[str]

    _exclude_attrs: List[str] = ["id", "uuid", "owner"]

    @classmethod
    def get_type(cls) -> str:
        return cls.__name__

    async def to_graphql(self, fields: dict = None) -> dict:

        response = {"id": self.uuid}

        for field_name in fields.keys():
            if field_name in ["id"]:
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

    async def refresh(self, session: AsyncSession, at=None, branch="main"):
        """Pull the latest state of the object from the database."""

        # Might need ot check how to manage the default value
        raw_attrs = self._get_item_raw(self.id, at=at, branch=branch, session=session)
        for item in raw_attrs:
            if item[1] != getattr(self, item[0]):
                setattr(self, item[0], item[1])

        return True

    async def _create(self, session: AsyncSession, id=None, branch="main"):
        """Create a new node in the database."""

        node_type = self.get_type()

        attrs = []
        for attr_name, attr in self.__fields__.items():
            if attr_name in self._exclude_attrs:
                continue
            attrs.append(f"{attr_name}: '{getattr(self, attr_name)}'")

        query = """
        CREATE (n:%s { uuid: $uuid, %s })
        RETURN n
        """ % (
            node_type,
            ", ".join(attrs),
        )

        params = {"uuid": str(uuid.uuid4())}

        results = await execute_write_query_async(session=session, query=query, params=params)
        if not results:
            raise Exception("Unexpected error, unable to create the new node.")

        node = results[0][0]

        self.id = node.element_id
        self.uuid = node["uuid"]

        return True

    async def _update(self, session: AsyncSession):
        """Update the node in the database if needed."""

        attrs = []
        for attr_name, attr in self.__fields__.items():
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
            raise Exception(f"Unexpected error, unable to update the node {self.id} / {self.uuid}.")

        results[0][0]

        return True

    @classmethod
    async def get(cls, id, session: AsyncSession):
        """Get a node from the database identied by its ID."""

        node = await cls._get_item_raw(id=id, session=session)
        if node:
            return cls._convert_node_to_obj(node)

        return None

    @classmethod
    async def _get_item_raw(cls, id, session: AsyncSession):

        query = (
            """
        MATCH (n:%s)
        WHERE ID(n) = $node_id OR n.uuid = $node_id
        RETURN n
        """
            % cls.get_type()
        )

        params = {"node_id": id}

        results = await execute_read_query_async(session=session, query=query, params=params)
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
        return cls(**attrs)

    @classmethod
    async def get_list(cls, session: AsyncSession, limit: int = 1000) -> List[SelfNode]:

        query = (
            """
        MATCH (n:%s)
        RETURN n
        ORDER BY ID(n)
        LIMIT $limit
        """
            % cls.get_type()
        )

        params = {"limit": 1000}

        results = await execute_read_query_async(session=session, query=query, params=params)
        return [cls._convert_node_to_obj(node.values()[0]) for node in results]
