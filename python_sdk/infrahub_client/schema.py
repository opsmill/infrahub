from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Dict, Optional

from infrahub_client.exceptions import SchemaNotFound
from infrahub_client.models import NodeSchema, SchemaRoot
from infrahub_client.queries import QUERY_SCHEMA

if TYPE_CHECKING:
    from infrahub_client import InfrahubClient


def flatten_dict(data):
    return {key: value.get("value") for key, value in data.items() if not isinstance(value, (list))}


class InfrahubSchema:
    """
    client.schema.get(branch="name", model="xxx")
    client.schema.all(branch="xxx")
    client.schema.validate()
    client.schema.add()
    client.schema.node.add()
    """

    def __init__(self, client: InfrahubClient):
        self.client = client
        self.cache: dict = defaultdict(lambda: dict)

    def validate(self, data):
        SchemaRoot(**data)
        return True

    async def get(self, model: str, branch: Optional[str] = None, refresh: bool = False) -> NodeSchema:
        branch = branch or self.client.default_branch

        if refresh:
            self.cache[branch] = await self.fetch(branch=branch)

        if branch in self.cache and model in self.cache[branch]:
            return self.cache[branch][model]

        # Fetching the latest schema from the server if we didn't fetch it earlier
        #   because we coulnd't find the object on the local cache
        if not refresh:
            self.cache[branch] = await self.fetch(branch=branch)

        if branch in self.cache and model in self.cache[branch]:
            return self.cache[branch][model]

        raise SchemaNotFound(identifier=model)

    async def all(self, branch: Optional[str] = None, refresh: bool = False) -> Dict[str, NodeSchema]:
        branch = branch or self.client.default_branch
        if refresh or branch not in self.cache:
            self.cache[branch] = await self.fetch(branch=branch)

        return self.cache[branch]

    async def fetch(self, branch: str) -> Dict[str, NodeSchema]:
        response = await self.client.execute_graphql(query=QUERY_SCHEMA, branch_name=branch)

        nodes = {}
        for node_schema in response["node_schema"]:
            data = flatten_dict(node_schema)
            data["attributes"] = [flatten_dict(attr) for attr in node_schema["attributes"]]
            data["relationships"] = [flatten_dict(rel) for rel in node_schema["relationships"]]

            node = NodeSchema(**data)
            nodes[node.kind] = node

        return nodes
