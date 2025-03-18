from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from infrahub.core.constants.schema import FlagProperty, NodeProperty
from infrahub.core.registry import registry

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class ValuePropertyData(BaseModel):
    name: str
    type: str
    value: str


class NodePropertyData(BaseModel):
    name: str
    peer_id: str


class FlagPropertyMixin:
    _flag_properties: list[str] = [v.value for v in FlagProperty]

    is_visible = True
    is_protected = False

    def _init_flag_property_mixin(self, kwargs: dict | None = None) -> None:
        if not kwargs:
            return

        for flag in self._flag_properties:
            if flag in kwargs.keys():
                setattr(self, flag, kwargs.get(flag))


class NodePropertyMixin:
    _node_properties: list[str] = [v.value for v in NodeProperty]

    branch: Branch
    at: Timestamp

    def _init_node_property_mixin(self, kwargs: dict | None = None) -> None:
        for node in self._node_properties:
            setattr(self, f"_{node}", None)
            setattr(self, f"{node}_id", None)

        if not kwargs:
            return

        for node in self._node_properties:
            if node in kwargs.keys():
                setattr(self, node, kwargs.get(node))
            if f"{node}_id" in kwargs.keys():
                setattr(self, f"{node}_id", kwargs.get(f"{node}_id"))

    @property
    def source(self) -> Node:
        return self._get_node_property_from_cache(name="source")

    @source.setter
    def source(self, value: str | Node | UUID) -> None:
        self._set_node_property(name="source", value=value)

    @property
    def owner(self) -> Node:
        return self._get_node_property_from_cache(name="owner")

    @owner.setter
    def owner(self, value: str | Node | UUID | None) -> None:
        self._set_node_property(name="owner", value=value)

    def clear_owner(self) -> None:
        self._set_node_property(name="owner", value=None)

    async def get_source(self, db: InfrahubDatabase) -> Node | None:
        return await self._get_node_property(name="source", db=db)

    def clear_source(self) -> None:
        self._set_node_property(name="source", value=None)

    def set_source(self, value: str | Node | UUID) -> None:
        self._set_node_property(name="source", value=value)

    async def get_owner(self, db: InfrahubDatabase) -> Node | None:
        return await self._get_node_property(name="owner", db=db)

    def set_owner(self, value: str | Node | UUID) -> None:
        self._set_node_property(name="owner", value=value)

    def _get_node_property_from_cache(self, name: str) -> Node:
        """Return the node attribute if it's already present locally,
        Otherwise raise an exception
        """
        item = getattr(self, f"_{name}", None)
        if not item:
            raise LookupError(
                f"The property {name} is not present locally, you must retrive it with get_{name}() instead."
            )

        return item

    async def _get_node_property(self, db: InfrahubDatabase, name: str) -> Node | None:
        """Return the node attribute.
        If the node is already present in cache, serve from the cache
        If the node is not present, query it on the fly using the node_id
        """
        if getattr(self, f"_{name}") is None:
            await self._retrieve_node_property(db=db, name=name)

        return getattr(self, f"_{name}", None)

    def _set_node_property(self, name: str, value: str | Node | UUID | None) -> None:
        """Set the value of the node_property.
        If the value is a string, we assume it's an ID and we'll save it to query it later (if needed)
        If the value is a Node, we save the node and we extract the ID
        if the value is None, we just initialize the 2 variables."""

        if isinstance(value, str | UUID):
            setattr(self, f"{name}_id", value)
            setattr(self, f"_{name}", None)
        elif isinstance(value, dict) and "id" in value:
            setattr(self, f"{name}_id", value["id"])
            setattr(self, f"_{name}", None)
        elif hasattr(value, "_schema"):
            setattr(self, f"_{name}", value)
            setattr(self, f"{name}_id", getattr(value, "id", None))
        elif value is None:
            setattr(self, f"_{name}", None)
            setattr(self, f"{name}_id", None)
        else:
            raise ValueError("Unable to process the node property")

    async def _retrieve_node_property(self, db: InfrahubDatabase, name: str) -> None:
        """Query the node associated with this node_property from the database."""

        node = await registry.manager.get_one(db=db, id=getattr(self, f"{name}_id"), branch=self.branch, at=self.at)
        setattr(self, f"_{name}", node)
        if node:
            setattr(self, f"{name}_id", node.id)
