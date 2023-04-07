from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from infrahub_client.exceptions import SchemaNotFound

if TYPE_CHECKING:
    from infrahub_client.client import InfrahubClient, InfrahubClientSync


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
    inherit_from: Optional[List[str]] = Field(default_factory=list)
    groups: Optional[List[str]] = Field(default_factory=list)
    branch: bool = True
    default_filter: Optional[str]
    filters: List[FilterSchema] = Field(default_factory=list)


class NodeExtensionSchema(BaseModel):
    name: Optional[str]
    kind: str
    description: Optional[str]
    label: Optional[str]
    inherit_from: Optional[List[str]] = Field(default_factory=list)
    groups: Optional[List[str]] = Field(default_factory=list)
    branch: Optional[bool]
    default_filter: Optional[str]
    attributes: List[AttributeSchema] = Field(default_factory=list)
    relationships: List[RelationshipSchema] = Field(default_factory=list)


class GroupSchema(BaseModel):
    name: str
    kind: str
    description: Optional[str]


class SchemaRoot(BaseModel):
    version: str
    generics: List[GenericSchema] = Field(default_factory=list)
    nodes: List[NodeSchema] = Field(default_factory=list)
    groups: List[GroupSchema] = Field(default_factory=list)
    # node_extensions: List[NodeExtensionSchema] = Field(default_factory=list)


class InfrahubSchemaBase:
    def validate(self, data: dict[str, Any]) -> bool:
        SchemaRoot(**data)

        # Add additional validation to ensure that all nodes references in relationships and extensions are present in the schema

        return True


class InfrahubSchema(InfrahubSchemaBase):
    """
    client.schema.get(branch="name", kind="xxx")
    client.schema.all(branch="xxx")
    client.schema.validate()
    client.schema.add()
    client.schema.node.add()
    """

    def __init__(self, client: InfrahubClient):
        self.client = client
        self.cache: dict = defaultdict(lambda: dict)

    async def get(self, kind: str, branch: Optional[str] = None, refresh: bool = False) -> NodeSchema:
        branch = branch or self.client.default_branch

        if refresh:
            self.cache[branch] = await self.fetch(branch=branch)

        if branch in self.cache and kind in self.cache[branch]:
            return self.cache[branch][kind]

        # Fetching the latest schema from the server if we didn't fetch it earlier
        #   because we coulnd't find the object on the local cache
        if not refresh:
            self.cache[branch] = await self.fetch(branch=branch)

        if branch in self.cache and kind in self.cache[branch]:
            return self.cache[branch][kind]

        raise SchemaNotFound(identifier=kind)

    async def all(self, branch: Optional[str] = None, refresh: bool = False) -> Dict[str, NodeSchema]:
        """Retrieve the entire schema for a given branch.

        if present in cache, the schema will be served from the cache, unless refresh is set to True
        if the schema is not present in the cache, it will be fetched automatically from the server

        Args:
            branch (str, optional): Name of the branch to query. Defaults to default_branch.
            refresh (bool, optional): Force a refresh of the schema. Defaults to False.

        Returns:
            Dict[str, NodeSchema]: Dictionnary of all schema organized by kind
        """
        branch = branch or self.client.default_branch
        if refresh or branch not in self.cache:
            self.cache[branch] = await self.fetch(branch=branch)

        return self.cache[branch]

    async def load(self, schema: dict, branch: Optional[str] = None) -> Tuple[bool, Optional[dict]]:
        branch = branch or self.client.default_branch
        url = f"{self.client.address}/schema/load?branch={branch}"
        response = await self.client._post(url=url, timeout=30, payload=schema)

        if response.status_code == 202:
            return True, None

        if response.status_code == 422:
            return False, response.json()

        response.raise_for_status()
        return False, None

    async def fetch(self, branch: str) -> Dict[str, NodeSchema]:
        """Fetch the schema from the server for a given branch.

        Args:
            branch (str): Name of the branch to fetch the schema for.

        Returns:
            Dict[str, NodeSchema]: Dictionnary of all schema organized by kind
        """
        url = f"{self.client.address}/schema/?branch={branch}"
        response = await self.client._get(url=url, timeout=2)
        response.raise_for_status()

        nodes = {}
        for node_schema in response.json()["nodes"]:
            node = NodeSchema(**node_schema)
            nodes[node.kind] = node

        return nodes


class InfrahubSchemaSync(InfrahubSchemaBase):
    def __init__(self, client: InfrahubClientSync):
        self.client = client
        self.cache: dict = defaultdict(lambda: dict)

    def all(self, branch: Optional[str] = None, refresh: bool = False) -> Dict[str, NodeSchema]:
        """Retrieve the entire schema for a given branch.

        if present in cache, the schema will be served from the cache, unless refresh is set to True
        if the schema is not present in the cache, it will be fetched automatically from the server

        Args:
            branch (str, optional): Name of the branch to query. Defaults to default_branch.
            refresh (bool, optional): Force a refresh of the schema. Defaults to False.

        Returns:
            Dict[str, NodeSchema]: Dictionnary of all schema organized by kind
        """
        branch = branch or self.client.default_branch
        if refresh or branch not in self.cache:
            self.cache[branch] = self.fetch(branch=branch)

        return self.cache[branch]

    def get(self, kind: str, branch: Optional[str] = None, refresh: bool = False) -> NodeSchema:
        branch = branch or self.client.default_branch

        if refresh:
            self.cache[branch] = self.fetch(branch=branch)

        if branch in self.cache and kind in self.cache[branch]:
            return self.cache[branch][kind]

        # Fetching the latest schema from the server if we didn't fetch it earlier
        #   because we coulnd't find the object on the local cache
        if not refresh:
            self.cache[branch] = self.fetch(branch=branch)

        if branch in self.cache and kind in self.cache[branch]:
            return self.cache[branch][kind]

        raise SchemaNotFound(identifier=kind)

    def fetch(self, branch: str) -> Dict[str, NodeSchema]:
        """Fetch the schema from the server for a given branch.

        Args:
            branch (str): Name of the branch to fetch the schema for.

        Returns:
            Dict[str, NodeSchema]: Dictionnary of all schema organized by kind
        """
        url = f"{self.client.address}/schema/?branch={branch}"
        response = self.client._get(url=url, timeout=2)
        response.raise_for_status()

        nodes = {}
        for node_schema in response.json()["nodes"]:
            node = NodeSchema(**node_schema)
            nodes[node.kind] = node

        return nodes

    def load(self, schema: dict, branch: Optional[str] = None) -> Tuple[bool, Optional[dict]]:
        branch = branch or self.client.default_branch
        url = f"{self.client.address}/schema/load?branch={branch}"
        response = self.client._post(url=url, timeout=30, payload=schema)

        if response.status_code == 202:
            return True, None

        if response.status_code == 422:
            return False, response.json()

        response.raise_for_status()
        return False, None
