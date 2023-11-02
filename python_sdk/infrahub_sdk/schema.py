from __future__ import annotations

from collections import defaultdict
from enum import Enum
from pathlib import Path  # noqa: TCH003
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    MutableMapping,
    Optional,
    Tuple,
    Union,
)

from pydantic import BaseModel, Field

from infrahub_sdk.exceptions import SchemaNotFound, ValidationError

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient, InfrahubClientSync

# pylint: disable=redefined-builtin


# ---------------------------------------------------------------------------------
# Repository Configuration file
# ---------------------------------------------------------------------------------
class InfrahubRepositoryRFileConfig(BaseModel):
    name: str
    query: str
    repository: str
    template_path: Path


class InfrahubRepositoryConfig(BaseModel):
    schemas: List[Path] = Field(default_factory=list)
    rfiles: Optional[List[InfrahubRepositoryRFileConfig]]


# ---------------------------------------------------------------------------------
# Main Infrahub Schema File
# ---------------------------------------------------------------------------------
class FilterSchema(BaseModel):
    name: str
    kind: str
    description: Optional[str]


class RelationshipCardinality(str, Enum):
    ONE = "one"
    MANY = "many"


class BranchSupportType(str, Enum):
    AWARE = "aware"
    AGNOSTIC = "agnostic"
    LOCAL = "local"


class RelationshipKind(str, Enum):
    GENERIC = "Generic"
    ATTRIBUTE = "Attribute"
    COMPONENT = "Component"
    PARENT = "Parent"
    GROUP = "Group"


class AttributeSchema(BaseModel):
    name: str
    kind: str
    label: Optional[str]
    description: Optional[str]
    default_value: Optional[Any]
    inherited: bool = False
    unique: bool = False
    branch: Optional[BranchSupportType]
    optional: bool = False


class RelationshipSchema(BaseModel):
    name: str
    peer: str
    kind: RelationshipKind = RelationshipKind.GENERIC
    label: Optional[str]
    description: Optional[str]
    identifier: Optional[str]
    inherited: bool = False
    cardinality: str = "many"
    branch: Optional[BranchSupportType]
    optional: bool = True
    filters: List[FilterSchema] = Field(default_factory=list)


class BaseNodeSchema(BaseModel):
    name: str
    label: Optional[str]
    namespace: str
    description: Optional[str]
    attributes: List[AttributeSchema] = Field(default_factory=list)
    relationships: List[RelationshipSchema] = Field(default_factory=list)
    filters: List[FilterSchema] = Field(default_factory=list)

    @property
    def kind(self) -> str:
        return self.namespace + self.name

    def get_field(self, name: str, raise_on_error: bool = True) -> Union[AttributeSchema, RelationshipSchema, None]:
        if attribute_field := self.get_attribute(name, raise_on_error=False):
            return attribute_field

        if relationship_field := self.get_relationship(name, raise_on_error=False):
            return relationship_field

        if not raise_on_error:
            return None

        raise ValueError(f"Unable to find the field {name}")

    def get_attribute(self, name: str, raise_on_error: bool = True) -> Union[AttributeSchema, None]:
        for item in self.attributes:
            if item.name == name:
                return item

        if not raise_on_error:
            return None

        raise ValueError(f"Unable to find the attribute {name}")

    def get_relationship(self, name: str, raise_on_error: bool = True) -> Union[RelationshipSchema, None]:
        for item in self.relationships:
            if item.name == name:
                return item

        if not raise_on_error:
            return None

        raise ValueError(f"Unable to find the relationship {name}")

    def get_relationship_by_identifier(self, id: str, raise_on_error: bool = True) -> Union[RelationshipSchema, None]:
        for item in self.relationships:
            if item.identifier == id:
                return item

        if not raise_on_error:
            return None

        raise ValueError(f"Unable to find the relationship {id}")

    @property
    def attribute_names(self) -> List[str]:
        return [item.name for item in self.attributes]

    @property
    def relationship_names(self) -> List[str]:
        return [item.name for item in self.relationships]

    @property
    def mandatory_input_names(self) -> List[str]:
        return self.mandatory_attribute_names + self.mandatory_relationship_names

    @property
    def mandatory_attribute_names(self) -> List[str]:
        return [item.name for item in self.attributes if not item.optional and item.default_value is None]

    @property
    def mandatory_relationship_names(self) -> List[str]:
        return [item.name for item in self.relationships if not item.optional]

    @property
    def local_attributes(self) -> List[AttributeSchema]:
        return [item for item in self.attributes if not item.inherited]

    @property
    def local_relationships(self) -> List[RelationshipSchema]:
        return [item for item in self.relationships if not item.inherited]

    @property
    def unique_attributes(self) -> List[AttributeSchema]:
        return [item for item in self.attributes if item.unique]


class GenericSchema(BaseNodeSchema):
    """A Generic can be either an Interface or a Union depending if there are some Attributes or Relationships defined."""

    used_by: List[str] = Field(default_factory=list)


class NodeSchema(BaseNodeSchema):
    inherit_from: List[str] = Field(default_factory=list)
    groups: List[str] = Field(default_factory=list)
    branch: Optional[BranchSupportType]
    default_filter: Optional[str]


class NodeExtensionSchema(BaseModel):
    name: Optional[str]
    kind: str
    description: Optional[str]
    label: Optional[str]
    inherit_from: List[str] = Field(default_factory=list)
    groups: List[str] = Field(default_factory=list)
    branch: Optional[BranchSupportType]
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
    def validate(self, data: dict[str, Any]) -> None:
        SchemaRoot(**data)

    def validate_data_against_schema(self, schema: Union[NodeSchema, GenericSchema], data: dict) -> None:
        for key in data.keys():
            if key not in schema.relationship_names + schema.attribute_names:
                identifier = f"{schema.kind}"
                raise ValidationError(
                    identifier=identifier,
                    message=f"{key} is not a valid value for {identifier}",
                )

    def generate_payload_create(
        self,
        schema: Union[NodeSchema, GenericSchema],
        data: dict,
        source: Optional[str] = None,
        owner: Optional[str] = None,
        is_protected: Optional[bool] = None,
        is_visible: Optional[bool] = None,
    ) -> Dict[str, Any]:
        obj_data: Dict[str, Any] = {}
        item_metadata: Dict[str, Any] = {}
        if source:
            item_metadata["source"] = str(source)
        if owner:
            item_metadata["owner"] = str(owner)
        if is_protected is not None:
            item_metadata["is_protected"] = is_protected
        if is_visible is not None:
            item_metadata["is_visible"] = is_visible

        for key, value in data.items():
            obj_data[key] = {}
            if key in schema.attribute_names:
                obj_data[key] = {"value": value}
                obj_data[key].update(item_metadata)
            elif key in schema.relationship_names:
                rel = schema.get_relationship(name=key)
                if rel:
                    if rel.cardinality == "one":
                        obj_data[key] = {"id": str(value)}
                        obj_data[key].update(item_metadata)
                    elif rel.cardinality == "many":
                        obj_data[key] = [{"id": str(item)} for item in value]
                        for item in obj_data[key]:
                            item.update(item_metadata)

        return obj_data


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

    async def get(
        self, kind: str, branch: Optional[str] = None, refresh: bool = False
    ) -> Union[NodeSchema, GenericSchema]:
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

    async def all(
        self, branch: Optional[str] = None, refresh: bool = False
    ) -> MutableMapping[str, Union[NodeSchema, GenericSchema]]:
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

    async def load(self, schemas: List[dict], branch: Optional[str] = None) -> Tuple[bool, Optional[dict]]:
        branch = branch or self.client.default_branch
        url = f"{self.client.address}/api/schema/load?branch={branch}"
        response = await self.client._post(url=url, timeout=60, payload={"schemas": schemas})

        if response.status_code == 202:
            return True, None

        if response.status_code == 422:
            return False, response.json()

        response.raise_for_status()
        return False, None

    async def fetch(self, branch: str) -> MutableMapping[str, Union[NodeSchema, GenericSchema]]:
        """Fetch the schema from the server for a given branch.

        Args:
            branch (str): Name of the branch to fetch the schema for.

        Returns:
            Dict[str, NodeSchema]: Dictionnary of all schema organized by kind
        """
        url = f"{self.client.address}/api/schema/?branch={branch}"
        response = await self.client._get(url=url)
        response.raise_for_status()

        data: MutableMapping[str, Any] = response.json()

        nodes: MutableMapping[str, Union[NodeSchema, GenericSchema]] = {}
        for node_schema in data.get("nodes", []):
            node = NodeSchema(**node_schema)
            nodes[node.kind] = node

        for generic_schema in data.get("generics", []):
            generic = GenericSchema(**generic_schema)
            nodes[generic.kind] = generic

        return nodes


class InfrahubSchemaSync(InfrahubSchemaBase):
    def __init__(self, client: InfrahubClientSync):
        self.client = client
        self.cache: dict = defaultdict(lambda: dict)

    def all(
        self, branch: Optional[str] = None, refresh: bool = False
    ) -> MutableMapping[str, Union[NodeSchema, GenericSchema]]:
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

    def get(self, kind: str, branch: Optional[str] = None, refresh: bool = False) -> Union[NodeSchema, GenericSchema]:
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

    def fetch(self, branch: str) -> MutableMapping[str, Union[NodeSchema, GenericSchema]]:
        """Fetch the schema from the server for a given branch.

        Args:
            branch (str): Name of the branch to fetch the schema for.

        Returns:
            Dict[str, NodeSchema]: Dictionnary of all schema organized by kind
        """
        url = f"{self.client.address}/api/schema/?branch={branch}"
        response = self.client._get(url=url)
        response.raise_for_status()

        data: MutableMapping[str, Any] = response.json()

        nodes: MutableMapping[str, Union[NodeSchema, GenericSchema]] = {}
        for node_schema in data.get("nodes", []):
            node = NodeSchema(**node_schema)
            nodes[node.kind] = node

        for generic_schema in data.get("generics", []):
            generic = GenericSchema(**generic_schema)
            nodes[generic.kind] = generic

        return nodes

    def load(self, schemas: List[dict], branch: Optional[str] = None) -> Tuple[bool, Optional[dict]]:
        branch = branch or self.client.default_branch
        url = f"{self.client.address}/api/schema/load?branch={branch}"
        response = self.client._post(url=url, timeout=60, payload={"schemas": schemas})

        if response.status_code == 202:
            return True, None

        if response.status_code == 422:
            return False, response.json()

        response.raise_for_status()
        return False, None
