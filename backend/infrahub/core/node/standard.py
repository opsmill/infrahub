from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Optional, Union, get_args, get_origin
from uuid import UUID

import ujson
from infrahub_sdk.uuidt import UUIDT
from pydantic import BaseModel

from infrahub.core.constants import NULL_VALUE
from infrahub.core.query.standard_node import (
    StandardNodeCreateQuery,
    StandardNodeDeleteQuery,
    StandardNodeGetItemQuery,
    StandardNodeGetListQuery,
    StandardNodeQuery,
    StandardNodeUpdateQuery,
)
from infrahub.exceptions import Error, InitializationError

if TYPE_CHECKING:
    from neo4j.graph import Node as Neo4jNode
    from pydantic.fields import FieldInfo
    from typing_extensions import Self

    from infrahub.core.query import Query
    from infrahub.database import InfrahubDatabase


class StandardNode(BaseModel):
    id: Optional[str] = None
    uuid: Optional[UUID] = None

    _query: type[StandardNodeQuery] = StandardNodeCreateQuery
    _exclude_attrs: list[str] = ["id", "uuid", "_query"]

    @classmethod
    def get_type(cls) -> str:
        return cls.__name__

    def get_id(self) -> str:
        if not self.id:
            raise ValueError("id isn't defined yet")
        return self.id

    @staticmethod
    def guess_field_type(field: FieldInfo) -> Any:
        """Return the type of a Pydantic model field.

        Here we mimic a fraction of the old Pydantic type analysis.
        https://github.com/pydantic/pydantic/blob/2e939dc3bfb88f54efb66f8f1a031ff22e4f9865/pydantic/fields.py#L539%23L758
        """
        annotation_origin = get_origin(field.annotation)
        annotation_args = get_args(field.annotation)

        if (annotation_origin == Union and len(annotation_args) == 2 and type(None) in annotation_args) or (
            annotation_origin is list and len(annotation_args)
        ):
            return get_origin(annotation_args[0]) or annotation_args[0]

        return annotation_origin or field.annotation

    def get_uuid(self) -> UUID:
        if self.uuid:
            return self.uuid

        raise InitializationError("The root node has not been initialized with a uuid")

    async def to_graphql(self, fields: dict) -> dict:
        response: dict[str, Any] = {"id": self.uuid}

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

    async def create(self, db: InfrahubDatabase) -> bool:
        """Create a new node in the database."""

        query: Query = await self._query.init(db=db, node=self)
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
    async def get(cls, id: str, db: InfrahubDatabase) -> Optional[Self]:
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
    def from_db(cls, node: Neo4jNode, extras: Optional[dict[str, Any]] = None) -> Self:
        """Convert a Neo4j Node to a Infrahub StandardNode

        Args:
            node (neo4j.graph.Node): Neo4j Node object

        Returns:
            StandardNode: Proper StandardNode object
        """

        attrs = {}
        node_data = dict(node)
        extras = extras or {}
        node_data.update(extras)
        attrs["id"] = node.element_id
        for key, value in node_data.items():
            if key not in cls.model_fields:
                continue

            field_type = cls.guess_field_type(cls.model_fields[key])

            if value == NULL_VALUE:
                attrs[key] = None
            elif issubclass(field_type, int | float | bool | str | UUID):
                attrs[key] = value
            elif isinstance(value, str | bytes):
                attrs[key] = ujson.loads(value)

        return cls(**attrs)

    def to_db(self) -> dict[str, Any]:
        data = {}

        if not self.uuid:
            data["uuid"] = str(UUIDT())
        else:
            data["uuid"] = str(self.uuid)

        for attr_name, field in self.model_fields.items():
            if attr_name in self._exclude_attrs:
                continue

            attr_value = getattr(self, attr_name)
            field_type = self.guess_field_type(field)

            if attr_value is None:
                data[attr_name] = NULL_VALUE
            elif inspect.isclass(field_type) and issubclass(field_type, BaseModel):
                if isinstance(attr_value, list):
                    clean_value = [item.model_dump() for item in attr_value]
                    data[attr_name] = ujson.dumps(clean_value)
                else:
                    data[attr_name] = attr_value.model_dump_json()
            elif issubclass(field_type, int | float | bool | str | UUID):
                data[attr_name] = attr_value
            else:
                data[attr_name] = ujson.dumps(attr_value)

        return data

    @classmethod
    async def get_list(
        cls,
        db: InfrahubDatabase,
        limit: int = 1000,
        ids: list[str] | None = None,
        name: str | None = None,
        **kwargs: dict[str, Any],
    ) -> list[Self]:
        query: Query = await StandardNodeGetListQuery.init(
            db=db, node_class=cls, ids=ids, node_name=name, limit=limit, **kwargs
        )
        await query.execute(db=db)

        return [cls.from_db(result.get("n")) for result in query.get_results()]
