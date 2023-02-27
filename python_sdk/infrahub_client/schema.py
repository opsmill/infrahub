from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import BaseModel, Field

from infrahub_client.exceptions import SchemaNotFound

if TYPE_CHECKING:
    from infrahub_client import InfrahubClient


class FilterSchema(BaseModel):
    name: str
    kind: str
    description: Optional[str]


class AttributeSchema(BaseModel):
    name: str
    kind: str
    label: Optional[str]
    description: Optional[str]
    default_value: Optional[Any]
    inherited: bool = False
    unique: bool = False
    branch: bool = True
    optional: bool = False


class RelationshipSchema(BaseModel):
    name: str
    peer: str
    label: Optional[str]
    description: Optional[str]
    identifier: Optional[str]
    inherited: bool = False
    cardinality: str = "many"
    branch: bool = True
    optional: bool = True
    filters: List[FilterSchema] = Field(default_factory=list)


class BaseNodeSchema(BaseModel):
    name: str
    kind: str
    description: Optional[str]
    attributes: List[AttributeSchema] = Field(default_factory=list)
    relationships: List[RelationshipSchema] = Field(default_factory=list)


class GenericSchema(BaseNodeSchema):
    """A Generic can be either an Interface or a Union depending if there are some Attributes or Relationships defined."""

    label: Optional[str]


class NodeSchema(BaseNodeSchema):
    label: Optional[str]
    inherit_from: List[str] = Field(default_factory=list)
    groups: List[str] = Field(default_factory=list)
    branch: bool = True
    default_filter: Optional[str]
    filters: List[FilterSchema] = Field(default_factory=list)


class GroupSchema(BaseModel):
    name: str
    kind: str
    description: Optional[str]


class SchemaRoot(BaseModel):
    version: str
    generics: List[GenericSchema] = Field(default_factory=list)
    nodes: List[NodeSchema] = Field(default_factory=list)
    groups: List[GroupSchema] = Field(default_factory=list)


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
        url = f"{self.client.address}/schema?branch={branch}"
        response = await self.client.get(url=url, timeout=2)
        response.raise_for_status()

        nodes = {}
        for node_schema in response.json()["nodes"]:
            node = NodeSchema(**node_schema)
            nodes[node.kind] = node

        return nodes
