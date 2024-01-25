from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from infrahub_sdk.timestamp import Timestamp
from infrahub_sdk.utils import dict_hash

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient, InfrahubClientSync


class InfrahubGroupContextBase():
    def __init__(self):
        self.related_nodes_ids: List[str] = []
        self.related_groups_ids: List[str] = []

    def add_related_nodes(self, ids: List[str] = None, update_group_context: Optional[bool] = False) -> None:
        conbined_bool = self.client.update_group_context and update_group_context
        if conbined_bool is True or conbined_bool is None:
            self.related_nodes_ids.extend(ids)

    def add_related_groups(self, ids: List[str] = None, update_group_context: Optional[bool] = False) -> None:
        conbined_bool = self.client.update_group_context and update_group_context
        if conbined_bool is True or conbined_bool is None:
            self.related_groups_ids.extend(ids)

class InfrahubGroupContext(InfrahubGroupContextBase):
    def __init__(self, client: InfrahubClient):
        self.client = client
        super().__init__()

    async def update_group(self, params: Optional[Dict[str, str]] = None) -> None:
        """Create or Update a GraphQLQueryGroup."""
        children: List[str] = []
        members: List[str] = []

        if self.related_groups_ids:
            children = self.related_groups_ids
        if self.related_nodes_ids:
            members = self.related_nodes_ids

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

        # TODO : create anoter "read" group based of the store items
        # Need to filters the store items inherited from CoreGroup to add them as children

class InfrahubGroupContextSync(InfrahubGroupContextBase):
    def __init__(self, client: InfrahubClientSync):
        self.client = client
        super().__init__()

    def update_group(self, params: Optional[Dict[str, str]] = None) -> None:
        """Create or Update a GraphQLQueryGroup."""
        children: List[str] = []
        members: List[str] = []

        if self.related_groups_ids:
            children = self.related_groups_ids
        if self.related_nodes_ids:
            members = self.related_nodes_ids

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

        # TODO : create anoter "read" group based of the store items
        # Need to filters the store items inherited from CoreGroup to add them as children
