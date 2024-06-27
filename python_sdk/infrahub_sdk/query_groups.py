from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from infrahub_sdk.constants import InfrahubClientMode
from infrahub_sdk.exceptions import NodeNotFoundError
from infrahub_sdk.utils import dict_hash

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient, InfrahubClientSync
    from infrahub_sdk.node import InfrahubNode, InfrahubNodeSync, RelatedNodeBase
    from infrahub_sdk.schema import MainSchemaTypes


class InfrahubGroupContextBase:
    """Base class for InfrahubGroupContext and InfrahubGroupContextSync"""

    def __init__(self) -> None:
        self.related_node_ids: list[str] = []
        self.related_group_ids: list[str] = []
        self.unused_member_ids: Optional[list[str]] = None
        self.unused_child_ids: Optional[list[str]] = None
        self.previous_members: Optional[list[RelatedNodeBase]] = None
        self.previous_children: Optional[list[RelatedNodeBase]] = None
        self.identifier: Optional[str] = None
        self.params: dict[str, str] = {}
        self.delete_unused_nodes: bool = False
        self.group_type: str = "CoreStandardGroup"

    def set_properties(
        self,
        identifier: str,
        params: Optional[dict[str, str]] = None,
        delete_unused_nodes: bool = False,
        group_type: Optional[str] = None,
    ) -> None:
        """Setter method to set the values of identifier and params.

        Args:
            identifier: The new value for the identifier.
            params: A dictionary with new values for the params.
        """
        self.identifier = identifier
        self.params = params or {}
        self.delete_unused_nodes = delete_unused_nodes
        self.group_type = group_type or self.group_type

    def _get_params_as_str(self) -> str:
        """Convert the params in dict format, into a string"""
        params_as_str: list[str] = []
        for key, value in self.params.items():
            params_as_str.append(f"{key}: {str(value)}")
        return ", ".join(params_as_str)

    def _generate_group_name(self, suffix: Optional[str] = None) -> str:
        group_name = self.identifier or "sdk"

        if suffix:
            group_name += f"-{suffix}"

        if self.params:
            group_name += f"-{dict_hash(self.params)}"

        return group_name

    def _generate_group_description(self, schema: MainSchemaTypes) -> str:
        """Generate the description of the group from the params
        and ensure it's not longer than the maximum length of the description field."""
        if not self.params:
            return ""

        description_str = self._get_params_as_str()
        description = schema.get_attribute(name="description")
        if description and description.max_length and len(description_str) > description.max_length:
            length = description.max_length - 5
            return description_str[:length] + "..."

        return description_str


class InfrahubGroupContext(InfrahubGroupContextBase):
    """Represents a Infrahub GroupContext in an asynchronous context."""

    def __init__(self, client: InfrahubClient) -> None:
        super().__init__()
        self.client = client

    async def get_group(self, store_peers: bool = False) -> Optional[InfrahubNode]:
        group_name = self._generate_group_name()
        try:
            group = await self.client.get(kind=self.group_type, name__value=group_name, include=["members", "children"])
        except NodeNotFoundError:
            return None

        if not store_peers:
            return group

        self.previous_members = group.members.peers  # type: ignore[attr-defined]
        self.previous_children = group.children.peers  # type: ignore[attr-defined]
        return group

    async def delete_unused(self) -> None:
        if self.previous_members and self.unused_member_ids:
            for member in self.previous_members:
                if member.id in self.unused_member_ids and member.typename:
                    await self.client.delete(kind=member.typename, id=member.id)

        if self.previous_children and self.unused_child_ids:
            for child in self.previous_children:
                if child.id in self.unused_child_ids and child.typename:
                    await self.client.delete(kind=child.typename, id=child.id)

    async def add_related_nodes(self, ids: list[str], update_group_context: Optional[bool] = None) -> None:
        """
        Add related Nodes IDs to the context.

        Args:
            ids (list[str]): List of node IDs to be added.
            update_group_context (Optional[bool], optional): Flag to control whether to update the group context.
        """
        if update_group_context is not False and (
            self.client.mode == InfrahubClientMode.TRACKING or self.client.update_group_context or update_group_context
        ):
            self.related_node_ids.extend(ids)

    async def add_related_groups(self, ids: list[str], update_group_context: Optional[bool] = None) -> None:
        """
        Add related Groups IDs to the context.

        Args:
            ids (list[str]): List of group IDs to be added.
            update_group_context (Optional[bool], optional): Flag to control whether to update the group context.
        """
        if update_group_context is not False and (
            self.client.mode == InfrahubClientMode.TRACKING or self.client.update_group_context or update_group_context
        ):
            self.related_group_ids.extend(ids)

    async def update_group(self) -> None:
        """
        Create or update (using upsert) a CoreStandardGroup to store all the Nodes and Groups used during an execution.
        """
        children: list[str] = []
        members: list[str] = []

        if self.related_group_ids:
            children = self.related_group_ids
        if self.related_node_ids:
            members = self.related_node_ids

        if not children and not members:
            return

        group_name = self._generate_group_name()
        schema = await self.client.schema.get(kind=self.group_type)
        description = self._generate_group_description(schema=schema)

        existing_group = None
        if self.delete_unused_nodes:
            existing_group = await self.get_group(store_peers=True)

        group = await self.client.create(
            kind=self.group_type,
            name=group_name,
            description=description,
            members=members,
            children=children,
        )
        await group.save(allow_upsert=True, update_group_context=False)

        if not existing_group:
            return

        # Calculate how many nodes should be deleted
        self.unused_member_ids = set(existing_group.members.peer_ids) - set(members)  # type: ignore
        self.unused_child_ids = set(existing_group.children.peer_ids) - set(children)  # type: ignore

        if not self.delete_unused_nodes:
            return

        await self.delete_unused()
        # TODO : create anoter "read" group. Could be based of the store items
        # Need to filters the store items inherited from CoreGroup to add them as children
        # Need to validate that it's UUIDas "key" if we want to implement other methods to store item


class InfrahubGroupContextSync(InfrahubGroupContextBase):
    """Represents a Infrahub GroupContext in an synchronous context."""

    def __init__(self, client: InfrahubClientSync) -> None:
        super().__init__()
        self.client = client

    def get_group(self, store_peers: bool = False) -> Optional[InfrahubNodeSync]:
        group_name = self._generate_group_name()
        try:
            group = self.client.get(kind=self.group_type, name__value=group_name, include=["members", "children"])
        except NodeNotFoundError:
            return None

        if not store_peers:
            return group

        self.previous_members = group.members.peers  # type: ignore[attr-defined]
        self.previous_children = group.children.peers  # type: ignore[attr-defined]
        return group

    def delete_unused(self) -> None:
        if self.previous_members and self.unused_member_ids:
            for member in self.previous_members:
                if member.id in self.unused_member_ids and member.typename:
                    self.client.delete(kind=member.typename, id=member.id)

        if self.previous_children and self.unused_child_ids:
            for child in self.previous_children:
                if child.id in self.unused_child_ids and child.typename:
                    self.client.delete(kind=child.typename, id=child.id)

    def add_related_nodes(self, ids: list[str], update_group_context: Optional[bool] = None) -> None:
        """
        Add related Nodes IDs to the context.

        Args:
            ids (list[str]): List of node IDs to be added.
            update_group_context (Optional[bool], optional): Flag to control whether to update the group context.
        """
        if update_group_context is not False and (
            self.client.mode == InfrahubClientMode.TRACKING or self.client.update_group_context or update_group_context
        ):
            self.related_node_ids.extend(ids)

    def add_related_groups(self, ids: list[str], update_group_context: Optional[bool] = None) -> None:
        """
        Add related Groups IDs to the context.

        Args:
            ids (list[str]): List of group IDs to be added.
            update_group_context (Optional[bool], optional): Flag to control whether to update the group context.
        """
        if update_group_context is not False and (
            self.client.mode == InfrahubClientMode.TRACKING or self.client.update_group_context or update_group_context
        ):
            self.related_group_ids.extend(ids)

    def update_group(self) -> None:
        """
        Create or update (using upsert) a CoreStandardGroup to store all the Nodes and Groups used during an execution.
        """
        children: list[str] = []
        members: list[str] = []

        if self.related_group_ids:
            children = self.related_group_ids
        if self.related_node_ids:
            members = self.related_node_ids

        if not children and not members:
            return

        group_name = self._generate_group_name()
        schema = self.client.schema.get(kind=self.group_type)
        description = self._generate_group_description(schema=schema)

        existing_group = None
        if self.delete_unused_nodes:
            existing_group = self.get_group(store_peers=True)

        group = self.client.create(
            kind=self.group_type,
            name=group_name,
            description=description,
            members=members,
            children=children,
        )
        group.save(allow_upsert=True, update_group_context=False)

        if not existing_group:
            return

        # Calculate how many nodes should be deleted
        self.unused_member_ids = set(existing_group.members.peer_ids) - set(members)  # type: ignore
        self.unused_child_ids = set(existing_group.children.peer_ids) - set(children)  # type: ignore

        if not self.delete_unused_nodes:
            return

        self.delete_unused()

        # TODO : create anoter "read" group. Could be based of the store items
        # Need to filters the store items inherited from CoreGroup to add them as children
        # Need to validate that it's UUIDas "key" if we want to implement other methods to store item
