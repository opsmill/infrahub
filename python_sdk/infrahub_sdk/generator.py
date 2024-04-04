from __future__ import annotations

import os
from abc import abstractmethod
from copy import deepcopy
from typing import TYPE_CHECKING, Dict, Optional

from git.repo import Repo

from infrahub_sdk.exceptions import UninitializedError

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient


class InfrahubGenerator:
    """Infrahub Generator class"""

    def __init__(
        self,
        query: str,
        client: InfrahubClient,
        branch: Optional[str] = None,
        root_directory: str = "",
        params: Optional[Dict] = None,
    ) -> None:
        self.query = query
        self.branch = branch
        self.git: Optional[Repo] = None
        self.params = params or {}
        self.root_directory = root_directory or os.getcwd()
        self._init_client = deepcopy(client)
        self._init_client.config.default_branch = self.branch_name
        self._client: Optional[InfrahubClient] = None

    @property
    def client(self) -> InfrahubClient:
        if self._client:
            return self._client
        raise UninitializedError("The client has not been initialized")

    @client.setter
    def client(self, value: InfrahubClient) -> None:
        self._client = value

    @property
    def branch_name(self) -> str:
        """Return the name of the current git branch."""

        if self.branch:
            return self.branch

        if not self.git:
            self.git = Repo(self.root_directory)

        self.branch = str(self.git.active_branch)

        return self.branch

    async def collect_data(self) -> Dict:
        """Query the result of the GraphQL Query defined in self.query and return the result"""

        return await self._init_client.query_gql_query(
            name=self.query, branch_name=self.branch_name, variables=self.params
        )

    async def run(self, identifier: str, data: Optional[dict] = None) -> None:
        """Execute the generator after collecting the data from the GraphQL query."""

        if not data:
            data = await self.collect_data()
        unpacked = data.get("data") or data

        async with self._init_client.start_tracking(
            identifier=identifier, params=self.params, delete_unused_nodes=True, group_type="CoreGeneratorGroup"
        ) as self.client:
            await self.generate(data=unpacked)

    @abstractmethod
    async def generate(self, data: dict) -> None:
        """Code to run the generator

        Any child class of the InfrahubGenerator us expected to provide this method. The method is expected
        to use the provided InfrahubClient contained in self.client to create or update any nodes in an idempotent
        way as the method could be executed multiple times. Typically this would be done by using:

        await new_or_updated_object.save(allow_upsert=True)

        The tracking system will be responsible for deleting nodes that are no longer required.
        """
