from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID  # noqa: TCH003

import ujson
from infrahub_sdk import UUIDT
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
    from neo4j.graph import Node as Neo4jNode
    from typing_extensions import Self

    from infrahub.core.query import Query
    from infrahub.database import InfrahubDatabase


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

    async def save(self, db: InfrahubDatabase) -> bool:
        """Create or Update the Node in the database."""

        if self.id:
            return await self.update(db=db)

        return await self.create(db=db)

    async def delete(self, db: InfrahubDatabase) -> None:
        """Delete the Node in the database."""

        query: Query = await StandardNodeDeleteQuery.init(db=db, node=self)
        await query.execute(db=db)

    async def refresh(self, db: InfrahubDatabase) -> bool:
        """Pull the latest state of the object from the database."""

        # Might need ot check how to manage the default value
        raw_attrs = self._get_item_raw(self.id, db=db)
        for item in raw_attrs:
            if item[1] != getattr(self, item[0]):
                setattr(self, item[0], item[1])

        return True

    async def create(self, db: InfrahubDatabase) -> bool:
        """Create a new node in the database."""

        query: Query = await StandardNodeCreateQuery.init(db=db, node=self)
        await query.execute(db=db)

        result = query.get_result()
        if not result:
            raise Error(f"Unable to create the node {self.get_type()}")
        node = result.get("n")

        self.id = node.element_id
        self.uuid = node["uuid"]

        return True

    async def update(self, db: InfrahubDatabase) -> bool:
        """Update the node in the database if needed."""

        query: Query = await StandardNodeUpdateQuery.init(db=db, node=self)
        await query.execute(db=db)
        result = query.get_result()

        if not result:
            raise Error(f"Unexpected error, unable to update the node {self.id} / {self.uuid}.")

        return True

    @classmethod
    async def get(cls, id: str, db: InfrahubDatabase) -> Self:
        """Get a node from the database identified by its ID."""

        node = await cls._get_item_raw(id=id, db=db)
        if node:
            return cls.from_db(node)

        return None

    @classmethod
    async def _get_item_raw(cls, id: str, db: InfrahubDatabase) -> Neo4jNode:
        query: Query = await StandardNodeGetItemQuery.init(db=db, node_id=id, node_type=cls.get_type())
        await query.execute(db=db)

        result = query.get_result()
        if not result:
            return None

        return result.get("n")

    @classmethod
    def from_db(cls, node: Neo4jNode) -> Self:
        """Convert a Neo4j Node to a Infrahub StandardNode

        Args:
            node (neo4j.graph.Node): Neo4j Node object

        Returns:
            StandardNode: Proper StandardNode object
        """

        attrs = {}
        node_data = dict(node)
        attrs["id"] = node.element_id
        for key, value in node_data.items():
            if key not in cls.model_fields:
                continue

            field_type = cls.__fields__[key].type_

            if value == "NULL":
                attrs[key] = None
            elif issubclass(field_type, (int, float, bool, str, UUID)):
                attrs[key] = value
            elif isinstance(value, (str, bytes)):
                attrs[key] = ujson.loads(value)

        return cls(**attrs)

    def to_db(self) -> Dict[str, Any]:
        data = {}

        if not self.uuid:
            data["uuid"] = str(UUIDT())
        else:
            data["uuid"] = self.uuid

        for attr_name, field in self.model_fields.items():
            if attr_name in self._exclude_attrs:
                continue

            attr_value = getattr(self, attr_name)
            field_type = field.type_

            if attr_value is None:
                data[attr_name] = "NULL"
            elif inspect.isclass(field_type) and issubclass(field_type, BaseModel):
                if isinstance(attr_value, list):
                    clean_value = [item.model_dump() for item in attr_value]
                    data[attr_name] = ujson.dumps(clean_value)
                else:
                    data[attr_name] = attr_value.json()
            elif issubclass(field_type, (int, float, bool, str, UUID)):
                data[attr_name] = attr_value
            else:
                data[attr_name] = ujson.dumps(attr_value)

        return data

    @classmethod
    async def get_list(
        cls,
        db: InfrahubDatabase,
        limit: int = 1000,
        ids: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Self]:
        query: Query = await StandardNodeGetListQuery.init(db=db, node_class=cls, ids=ids, limit=limit, **kwargs)
        await query.execute(db=db)

        return [cls.from_db(result.get("n")) for result in query.get_results()]
