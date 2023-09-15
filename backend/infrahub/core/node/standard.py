from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID  # noqa: TCH003

from pydantic import BaseModel

from infrahub.core.query.standard_node import (
    StandardNodeCreateQuery,
    StandardNodeDeleteQuery,
    StandardNodeGetItemQuery,
    StandardNodeGetListQuery,
    StandardNodeUpdateQuery,
)
from infrahub.exceptions import Error

# pylint: disable=redefined-builtin

if TYPE_CHECKING:
    from neo4j import AsyncSession
    from neo4j.graph import Node as Neo4jNode
    from typing_extensions import Self

    from infrahub.core.query import Query


class StandardNode(BaseModel):
    id: Optional[str] = None
    uuid: Optional[UUID] = None

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

    async def save(self, session: AsyncSession) -> bool:
        """Create or Update the Node in the database."""

        if self.id:
            return await self._update(session=session)

        return await self._create(session=session)

    async def delete(self, session: AsyncSession) -> None:
        """Delete the Node in the database."""

        query: Query = await StandardNodeDeleteQuery.init(session=session, node=self)
        await query.execute(session=session)

    async def refresh(self, session: AsyncSession) -> bool:
        """Pull the latest state of the object from the database."""

        # Might need ot check how to manage the default value
        raw_attrs = self._get_item_raw(self.id, session=session)
        for item in raw_attrs:
            if item[1] != getattr(self, item[0]):
                setattr(self, item[0], item[1])

        return True

    async def _create(self, session: AsyncSession) -> bool:
        """Create a new node in the database."""

        query: Query = await StandardNodeCreateQuery.init(session=session, node=self)
        await query.execute(session=session)

        result = query.get_result()
        if not result:
            raise Error(f"Unable to create the node {self.get_type()}")
        node = result.get("n")

        self.id = node.element_id
        self.uuid = node["uuid"]

        return True

    async def _update(self, session: AsyncSession) -> bool:
        """Update the node in the database if needed."""

        query: Query = await StandardNodeUpdateQuery.init(session=session, node=self)
        await query.execute(session=session)
        result = query.get_result()

        if not result:
            raise Error(f"Unexpected error, unable to update the node {self.id} / {self.uuid}.")

        return True

    @classmethod
    async def get(cls, id: str, session: AsyncSession) -> Self:
        """Get a node from the database identified by its ID."""

        node = await cls._get_item_raw(id=id, session=session)
        if node:
            return cls._convert_node_to_obj(node)

        return None

    @classmethod
    async def _get_item_raw(cls, id: str, session: AsyncSession) -> Neo4jNode:
        query: Query = await StandardNodeGetItemQuery.init(session=session, node_id=id, node_type=cls.get_type())
        await query.execute(session=session)

        result = query.get_result()
        if not result:
            return None

        return result.get("n")

    @classmethod
    def _convert_node_to_obj(cls, node: Neo4jNode) -> Self:
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
    async def get_list(
        cls,
        session: AsyncSession,
        limit: int = 1000,
        ids: Optional[List[str]] = None,
        name: Optional[str] = None,
        **kwargs,
    ) -> List[Self]:
        query: Query = await StandardNodeGetListQuery.init(
            session=session, node_class=cls, ids=ids, name=name, limit=limit, **kwargs
        )
        await query.execute(session=session)

        return [cls._convert_node_to_obj(result.get("n")) for result in query.get_results()]
