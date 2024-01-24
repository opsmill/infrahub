from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from infrahub_sdk.timestamp import Timestamp
from infrahub_sdk.utils import dict_hash

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient, InfrahubClientSync


class InfrahubGroupContextBase():
    def __init__(self):
        pass

class InfrahubGroupContext(InfrahubGroupContextBase):
    def __init__(self, client: InfrahubClient):
        self.client = client
        super().__init__()

    async def create_group(self, params: Optional[Dict[str, str]] = None) -> None:
        """Create or Update a GraphQLQueryGroup."""
        if self.client.query_group_identifier:
            group_name = self.client.query_group_identifier
        elif params:
            group_name = dict_hash(params)
        group_label = f"SDK Run {group_name})"

        self.group = await self.client.create(
            kind="CoreGraphQLQueryGroup",
            name=group_name,
            label=group_label
        )
        backup_client_update_group = self.client.update_group
        self.client.update_group = False
        await self.group.save(at=Timestamp(), allow_upsert=True, update_group=False)
        self.client.update_group = backup_client_update_group

    # async def __aenter__(self):
    #     await self.create_group()

    # async def __aexit__(self, exc_type, exc_val, exc_tb):
    #     # TODO ?
    #     pass

class InfrahubGroupContextSync(InfrahubGroupContextBase):
    def __init__(self, client: InfrahubClientSync):
        self.client = client
        super().__init__()

    def create_group(self, params: Optional[Dict[str, str]] = None) -> None:
        """Create or Update a GraphQLQueryGroup."""
        if self.client.query_group_identifier:
            group_name = self.client.query_group_identifier
        elif params:
            group_name = dict_hash(params)
        group_label = f"SDK Run {group_name})"

        self.group = self.client.create(
            kind="CoreGraphQLQueryGroup",
            name=group_name,
            label=group_label
        )
        backup_client_update_group = self.client.update_group
        self.client.update_group = False
        self.group.save(at=Timestamp(), allow_upsert=True, update_group=False)
        self.client.update_group = backup_client_update_group

    # def __enter__(self):
    #     self.create_group()

    # def __exit__(self, exc_type, exc_val, exc_tb):
        # TODO ?
        pass