from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from infrahub_sdk.timestamp import Timestamp
from infrahub_sdk.utils import dict_hash

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient, InfrahubClientSync


class InfrahubGroupContextBase:
    """Base class for InfrahubGroupContext and InfrahubGroupContextSync"""

    def __init__(self) -> None:
        self.related_nodes_ids: List[str] = []
        self.related_groups_ids: List[str] = []


class InfrahubGroupContext(InfrahubGroupContextBase):
    """Represents a Infrahub GroupContext in an asynchronous context."""

    def __init__(self, client: InfrahubClient) -> None:
        super().__init__()
        self.client = client

    async def add_related_nodes(self, ids: List[str], update_group_context: Optional[bool] = False) -> None:
        """
        Add related Nodes IDs to the context.

        Args:
            ids (List[str]): List of node IDs to be added.
            update_group_context (Optional[bool], optional): Flag to control whether to update the group context.
        """
        conbined_bool = self.client.update_group_context and update_group_context
        if conbined_bool is True or conbined_bool is None:
            self.related_nodes_ids.extend(ids)

    async def add_related_groups(self, ids: List[str], update_group_context: Optional[bool] = False) -> None:
        """
        Add related Groups IDs to the context.

        Args:
            ids (List[str]): List of group IDs to be added.
            update_group_context (Optional[bool], optional): Flag to control whether to update the group context.
        """
        conbined_bool = self.client.update_group_context and update_group_context
        if conbined_bool is True or conbined_bool is None:
            self.related_groups_ids.extend(ids)

    async def update_group(self, params: Optional[Dict[str, str]] = None) -> None:
        """
        Create or update (using upsert) a CoreStandGroup to store all the Nodes and Groups used during an execution.

        Args:
            params (Optional[Dict[str, str]], optional): Additional parameters for the group name.
        """
        children: List[str] = []
        members: List[str] = []

        if self.related_groups_ids:
            children = self.related_groups_ids
        if self.related_nodes_ids:
            members = self.related_nodes_ids

        if children or members:
            if self.client.context_identifier:
                group_name = f"{self.client.context_identifier}-saved"
            else:
                group_name = "sdk-saved"
            if params:
                group_name = f"saved-{dict_hash(params)}"
            group_label = f"SDK Run {group_name}"

            group = await self.client.create(
                kind="CoreStandardGroup",
                name=group_name,
                label=group_label,
                members=members,
                children=children,
            )
            await group.save(at=Timestamp(), allow_upsert=True, update_group_context=False)

        # TODO : create anoter "read" group. Could be based of the store items
        # Need to filters the store items inherited from CoreGroup to add them as children
        # Need to validate that it's UUIDas "key" if we want to implement other methods to store item


class InfrahubGroupContextSync(InfrahubGroupContextBase):
    """Represents a Infrahub GroupContext in an synchronous context."""

    def __init__(self, client: InfrahubClientSync) -> None:
        super().__init__()
        self.client = client

    def add_related_nodes(self, ids: List[str], update_group_context: Optional[bool] = False) -> None:
        """
        Add related Nodes IDs to the context.

        Args:
            ids (List[str]): List of node IDs to be added.
            update_group_context (Optional[bool], optional): Flag to control whether to update the group context.
        """
        conbined_bool = self.client.update_group_context and update_group_context
        if conbined_bool is True or conbined_bool is None:
            self.related_nodes_ids.extend(ids)

    def add_related_groups(self, ids: List[str], update_group_context: Optional[bool] = False) -> None:
        """
        Add related Groups IDs to the context.

        Args:
            ids (List[str]): List of group IDs to be added.
            update_group_context (Optional[bool], optional): Flag to control whether to update the group context.
        """
        conbined_bool = self.client.update_group_context and update_group_context
        if conbined_bool is True or conbined_bool is None:
            self.related_groups_ids.extend(ids)

    def update_group(self, params: Optional[Dict[str, str]] = None) -> None:
        """
        Create or update (using upsert) a CoreStandGroup to store all the Nodes and Groups used during an execution.

        Args:
            params (Optional[Dict[str, str]], optional): Additional parameters for the group name.
        """
        children: List[str] = []
        members: List[str] = []

        if self.related_groups_ids:
            children = self.related_groups_ids
        if self.related_nodes_ids:
            members = self.related_nodes_ids

        if children or members:
            if self.client.context_identifier:
                group_name = f"{self.client.context_identifier}-saved"
            else:
                group_name = "sdk-saved"
            if params:
                group_name = f"saved-{dict_hash(params)}"
            group_label = f"SDK Run {group_name}"

            group = self.client.create(
                kind="CoreStandardGroup",
                name=group_name,
                label=group_label,
                members=members,
                children=children,
            )
            group.save(at=Timestamp(), allow_upsert=True, update_group_context=False)

        # TODO : create anoter "read" group. Could be based of the store items
        # Need to filters the store items inherited from CoreGroup to add them as children
        # Need to validate that it's UUIDas "key" if we want to implement other methods to store item
