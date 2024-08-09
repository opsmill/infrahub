from __future__ import annotations

import os
from abc import abstractmethod
from typing import TYPE_CHECKING, Optional

from git.repo import Repo

from infrahub_sdk.exceptions import UninitializedError

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.node import InfrahubNode
    from infrahub_sdk.store import NodeStore


class InfrahubGenerator:
    """Infrahub Generator class"""

    def __init__(
        self,
        query: str,
        client: InfrahubClient,
        infrahub_node: type[InfrahubNode],
        branch: Optional[str] = None,
        root_directory: str = "",
        generator_instance: str = "",
        params: Optional[dict] = None,
        convert_query_response: bool = False,
    ) -> None:
        self.query = query
        self.branch = branch
        self.git: Optional[Repo] = None
        self.params = params or {}
        self.root_directory = root_directory or os.getcwd()
        self.generator_instance = generator_instance
        self._init_client = client.clone()
        self._init_client.config.default_branch = self._init_client.default_branch = self.branch_name
        self._client: Optional[InfrahubClient] = None
        self._nodes: list[InfrahubNode] = []
        self._related_nodes: list[InfrahubNode] = []
        self.infrahub_node = infrahub_node
        self.convert_query_response = convert_query_response

    @property
    def store(self) -> NodeStore:
        """The store will be populated with nodes based on the query during the collection of data if activated"""
        return self._init_client.store

    @property
    def nodes(self) -> list[InfrahubNode]:
        """Returns nodes collected and parsed during the data collection process if this feature is enables"""
        return self._nodes

    @property
    def related_nodes(self) -> list[InfrahubNode]:
        """Returns nodes collected and parsed during the data collection process if this feature is enables"""
        return self._related_nodes

    @property
    def subscribers(self) -> Optional[list[str]]:
        if self.generator_instance:
            return [self.generator_instance]
        return None

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

    async def collect_data(self) -> dict:
        """Query the result of the GraphQL Query defined in self.query and return the result"""

        data = await self._init_client.query_gql_query(
            name=self.query,
            branch_name=self.branch_name,
            variables=self.params,
            update_group=True,
            subscribers=self.subscribers,
        )
        unpacked = data.get("data") or data
        await self.process_nodes(data=unpacked)
        return data

    async def run(self, identifier: str, data: Optional[dict] = None) -> None:
        """Execute the generator after collecting the data from the GraphQL query."""

        if not data:
            data = await self.collect_data()
        unpacked = data.get("data") or data

        async with self._init_client.start_tracking(
            identifier=identifier, params=self.params, delete_unused_nodes=True, group_type="CoreGeneratorGroup"
        ) as self.client:
            await self.generate(data=unpacked)

    async def process_nodes(self, data: dict) -> None:
        if not self.convert_query_response:
            return

        await self._init_client.schema.all(branch=self.branch_name)

        for kind in data:
            if kind in self._init_client.schema.cache[self.branch_name]:
                for result in data[kind].get("edges", []):
                    node = await self.infrahub_node.from_graphql(
                        client=self._init_client, branch=self.branch_name, data=result
                    )
                    self._nodes.append(node)
                    await node._process_relationships(
                        node_data=result, branch=self.branch_name, related_nodes=self._related_nodes
                    )

        for node in self._nodes + self._related_nodes:
            if node.id:
                self._init_client.store.set(key=node.id, node=node)

    @abstractmethod
    async def generate(self, data: dict) -> None:
        """Code to run the generator

        Any child class of the InfrahubGenerator us expected to provide this method. The method is expected
        to use the provided InfrahubClient contained in self.client to create or update any nodes in an idempotent
        way as the method could be executed multiple times. Typically this would be done by using:

        await new_or_updated_object.save(allow_upsert=True)

        The tracking system will be responsible for deleting nodes that are no longer required.
        """
