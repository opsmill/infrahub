from __future__ import annotations

from uuid import UUID
from typing import TYPE_CHECKING, List, Union

if TYPE_CHECKING:
    from infrahub.core.node import Node


class FlagPropertyMixin:

    _flag_properties: List[str] = ["is_visible", "is_protected"]

    is_visible = True
    is_protected = False

    def _init_flag_property_mixin(self, kwargs: dict = None):
        if not kwargs:
            return

        for flag in self._flag_properties:
            if flag in kwargs.keys():
                setattr(self, flag, kwargs.get(flag))


class NodePropertyMixin:

    _node_properties: List[str] = ["source", "owner"]

    def _init_node_property_mixin(self, kwargs: dict = None):
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
    def source(self):
        return self._get_node_property("source")

    @source.setter
    def source(self, value):
        self._set_node_property("source", value)

    @property
    def owner(self):
        return self._get_node_property("owner")

    @owner.setter
    def owner(self, value):
        self._set_node_property("owner", value)

    def _get_node_property(self, name: str) -> Node:
        """Return the node attribute.
        If the node is already present in cache, serve from the cache
        If the node is not present, query it on the fly using the node_id
        """
        if getattr(self, f"_{name}") is None:
            self._retrieve_node_property(name)

        return getattr(self, f"_{name}", None)

    def _set_node_property(self, name: str, value: Union[Node, UUID]):
        """Set the value of the node_property.
        If the value is a string, we assume it's an ID and we'll save it to query it later (if needed)
        If the value is a Node, we save the node and we extract the ID
        if the value is None, we just initialize the 2 variables."""

        if isinstance(value, (str, UUID)):
            setattr(self, f"{name}_id", value)
            setattr(self, f"_{name}", None)
        elif isinstance(value, dict) and "id" in value:
            setattr(self, f"{name}_id", value["id"])
            setattr(self, f"_{name}", None)
        elif hasattr(value, "_schema"):
            setattr(self, f"_{name}", value)
            setattr(self, f"{name}_id", value.id)
        elif value is None:
            setattr(self, f"_{name}", None)
            setattr(self, f"{name}_id", None)
        else:
            raise ValueError("Unable to process the node property")

    def _retrieve_node_property(self, name: str):
        """Query the node associated with this node_property from the database."""
        from infrahub.core.manager import NodeManager

        node = NodeManager.get_one(getattr(self, f"{name}_id"), branch=self.branch, at=self.at)
        setattr(self, f"_{name}", node)
        if node:
            setattr(self, f"{name}_id", node.id)
