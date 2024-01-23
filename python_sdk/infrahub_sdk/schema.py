from __future__ import annotations

from collections import defaultdict
from enum import Enum
from pathlib import Path  # noqa: TCH003
from typing import TYPE_CHECKING, Any, Dict, List, MutableMapping, Optional, Tuple, TypedDict, TypeVar, Union
from urllib.parse import urlencode

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]

from infrahub_sdk.exceptions import SchemaNotFound, ValidationError
from infrahub_sdk.graphql import Mutation
from infrahub_sdk.utils import duplicates

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient, InfrahubClientSync
    from infrahub_sdk.node import InfrahubNode, InfrahubNodeSync

    InfrahubNodeTypes = Union[InfrahubNode, InfrahubNodeSync]

# pylint: disable=redefined-builtin


class DropdownMutationOptionalArgs(TypedDict):
    color: Optional[str]
    description: Optional[str]
    label: Optional[str]


ResourceClass = TypeVar("ResourceClass")

# ---------------------------------------------------------------------------------
# Repository Configuration file
# ---------------------------------------------------------------------------------


class InfrahubRepositoryConfigElement(pydantic.BaseModel):
    """Class to regroup all elements of the infrahub configuration for a repository for typing purpose."""


class InfrahubRepositoryArtifactDefinitionConfig(InfrahubRepositoryConfigElement):
    name: str = pydantic.Field(..., description="The name of the artifact definition")
    artifact_name: Optional[str] = pydantic.Field(
        default=None, description="Name of the artifact created from this definition"
    )
    parameters: Dict[str, Any] = pydantic.Field(
        ..., description="The input parameters required to render this artifact"
    )
    content_type: str = pydantic.Field(..., description="The content type of the rendered artifact")
    targets: str = pydantic.Field(..., description="The group to target when creating artifacts")
    transformation: str = pydantic.Field(..., description="The transformation to use.")


class InfrahubJinja2TransformConfig(InfrahubRepositoryConfigElement):
    name: str = pydantic.Field(..., description="The name of the transform")
    query: str = pydantic.Field(..., description="The name of the GraphQL Query")
    template_path: Path = pydantic.Field(..., description="The path within the repository of the template file")
    description: Optional[str] = pydantic.Field(default=None, description="Description for this transform")

    @property
    def template_path_value(self) -> str:
        return str(self.template_path)

    @property
    def payload(self) -> Dict[str, str]:
        data = self.dict(exclude_none=True)
        data["template_path"] = self.template_path_value
        return data


class InfrahubCheckDefinitionConfig(InfrahubRepositoryConfigElement):
    name: str = pydantic.Field(..., description="The name of the Check Definition")
    file_path: Path = pydantic.Field(..., description="The file within the repo with the check code.")
    parameters: Dict[str, Any] = pydantic.Field(
        default_factory=dict, description="The input parameters required to run this check"
    )
    targets: Optional[str] = pydantic.Field(
        default=None, description="The group to target when running this check, leave blank for global checks"
    )
    class_name: str = pydantic.Field(default="Check", description="The name of the check class to run.")


class InfrahubPythonTransformConfig(InfrahubRepositoryConfigElement):
    name: str = pydantic.Field(..., description="The name of the Transform")
    file_path: Path = pydantic.Field(..., description="The file within the repo with the transform code.")
    class_name: str = pydantic.Field(default="Transform", description="The name of the transform class to run.")


RESOURCE_MAP: Dict[Any, str] = {
    InfrahubJinja2TransformConfig: "jinja2_transforms",
    InfrahubCheckDefinitionConfig: "check_definitions",
    InfrahubRepositoryArtifactDefinitionConfig: "artifact_definitions",
    InfrahubPythonTransformConfig: "python_transforms",
}


class InfrahubRepositoryConfig(pydantic.BaseModel):
    check_definitions: List[InfrahubCheckDefinitionConfig] = pydantic.Field(default_factory=list)
    schemas: List[Path] = pydantic.Field(default_factory=list)
    jinja2_transforms: List[InfrahubJinja2TransformConfig] = pydantic.Field(default_factory=list)
    artifact_definitions: List[InfrahubRepositoryArtifactDefinitionConfig] = pydantic.Field(default_factory=list)
    python_transforms: List[InfrahubPythonTransformConfig] = pydantic.Field(default_factory=list)

    @pydantic.validator("jinja2_transforms", "check_definitions", "artifact_definitions", "python_transforms")
    @classmethod
    def unique_items(cls, v: Any, **kwargs: Dict[str, Any]) -> Any:  # pylint: disable=unused-argument
        names = [item.name for item in v]
        if dups := duplicates(names):
            raise ValueError(f"Found multiples element with the same names: {dups}")
        return v

    def _has_resource(self, resource_id: str, resource_type: type[ResourceClass], resource_field: str = "name") -> bool:
        for item in getattr(self, RESOURCE_MAP[resource_type]):
            if getattr(item, resource_field) == resource_id:
                return True
        return False

    def _get_resource(
        self, resource_id: str, resource_type: type[ResourceClass], resource_field: str = "name"
    ) -> ResourceClass:
        for item in getattr(self, RESOURCE_MAP[resource_type]):
            if getattr(item, resource_field) == resource_id:
                return item
        raise KeyError(f"Unable to find {resource_id!r} in {RESOURCE_MAP[resource_type]!r}")

    def has_jinja2_transform(self, name: str) -> bool:
        return self._has_resource(resource_id=name, resource_type=InfrahubJinja2TransformConfig)

    def get_jinja2_transform(self, name: str) -> InfrahubJinja2TransformConfig:
        return self._get_resource(resource_id=name, resource_type=InfrahubJinja2TransformConfig)

    def has_check_definition(self, name: str) -> bool:
        return self._has_resource(resource_id=name, resource_type=InfrahubCheckDefinitionConfig)

    def get_check_definition(self, name: str) -> InfrahubCheckDefinitionConfig:
        return self._get_resource(resource_id=name, resource_type=InfrahubCheckDefinitionConfig)

    def has_artifact_definition(self, name: str) -> bool:
        return self._has_resource(resource_id=name, resource_type=InfrahubRepositoryArtifactDefinitionConfig)

    def get_artifact_definition(self, name: str) -> InfrahubRepositoryArtifactDefinitionConfig:
        return self._get_resource(resource_id=name, resource_type=InfrahubRepositoryArtifactDefinitionConfig)

    def has_python_transform(self, name: str) -> bool:
        return self._has_resource(resource_id=name, resource_type=InfrahubPythonTransformConfig)

    def get_python_transform(self, name: str) -> InfrahubPythonTransformConfig:
        return self._get_resource(resource_id=name, resource_type=InfrahubPythonTransformConfig)


# ---------------------------------------------------------------------------------
# Main Infrahub Schema File
# ---------------------------------------------------------------------------------
class FilterSchema(pydantic.BaseModel):
    name: str
    kind: str
    description: Optional[str] = None


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
    HIERARCHY = "Hierarchy"


class DropdownMutation(str, Enum):
    add = "SchemaDropdownAdd"
    remove = "SchemaDropdownRemove"


class EnumMutation(str, Enum):
    add = "SchemaEnumAdd"
    remove = "SchemaEnumRemove"


class AttributeSchema(pydantic.BaseModel):
    name: str
    kind: str
    label: Optional[str] = None
    description: Optional[str] = None
    default_value: Optional[Any] = None
    inherited: bool = False
    unique: bool = False
    branch: Optional[BranchSupportType] = None
    optional: bool = False
    read_only: bool = False
    choices: Optional[List[Dict[str, str]]] = None
    enum: Optional[List[Union[str, int]]] = None


class RelationshipSchema(pydantic.BaseModel):
    name: str
    peer: str
    kind: RelationshipKind = RelationshipKind.GENERIC
    label: Optional[str] = None
    description: Optional[str] = None
    identifier: Optional[str] = None
    inherited: bool = False
    cardinality: str = "many"
    branch: Optional[BranchSupportType] = None
    optional: bool = True
    filters: List[FilterSchema] = pydantic.Field(default_factory=list)


class BaseNodeSchema(pydantic.BaseModel):
    name: str
    label: Optional[str] = None
    namespace: str
    description: Optional[str] = None
    attributes: List[AttributeSchema] = pydantic.Field(default_factory=list)
    relationships: List[RelationshipSchema] = pydantic.Field(default_factory=list)
    filters: List[FilterSchema] = pydantic.Field(default_factory=list)

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

    used_by: List[str] = pydantic.Field(default_factory=list)


class NodeSchema(BaseNodeSchema):
    inherit_from: List[str] = pydantic.Field(default_factory=list)
    groups: List[str] = pydantic.Field(default_factory=list)
    branch: Optional[BranchSupportType] = None
    default_filter: Optional[str] = None


class NodeExtensionSchema(pydantic.BaseModel):
    name: Optional[str] = None
    kind: str
    description: Optional[str] = None
    label: Optional[str] = None
    inherit_from: List[str] = pydantic.Field(default_factory=list)
    groups: List[str] = pydantic.Field(default_factory=list)
    branch: Optional[BranchSupportType] = None
    default_filter: Optional[str] = None
    attributes: List[AttributeSchema] = pydantic.Field(default_factory=list)
    relationships: List[RelationshipSchema] = pydantic.Field(default_factory=list)


class GroupSchema(pydantic.BaseModel):
    name: str
    kind: str
    description: Optional[str] = None


class SchemaRoot(pydantic.BaseModel):
    version: str
    generics: List[GenericSchema] = pydantic.Field(default_factory=list)
    nodes: List[NodeSchema] = pydantic.Field(default_factory=list)
    groups: List[GroupSchema] = pydantic.Field(default_factory=list)
    # node_extensions: List[NodeExtensionSchema] = pydantic.Field(default_factory=list)


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
        self, branch: Optional[str] = None, refresh: bool = False, namespaces: Optional[List[str]] = None
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
            self.cache[branch] = await self.fetch(branch=branch, namespaces=namespaces)

        return self.cache[branch]

    async def load(self, schemas: List[dict], branch: Optional[str] = None) -> Tuple[bool, Optional[dict]]:
        branch = branch or self.client.default_branch
        url = f"{self.client.address}/api/schema/load?branch={branch}"
        response = await self.client._post(url=url, timeout=120, payload={"schemas": schemas})

        if response.status_code == 202:
            return True, None

        if response.status_code == 422:
            return False, response.json()

        response.raise_for_status()
        return False, None

    async def _get_kind_and_attribute_schema(
        self, kind: Union[str, InfrahubNodeTypes], attribute: str, branch: Optional[str] = None
    ) -> Tuple[str, AttributeSchema]:
        node_kind: str = kind._schema.kind if not isinstance(kind, str) else kind
        node_schema = await self.client.schema.get(kind=node_kind, branch=branch)
        schema_attr = node_schema.get_attribute(attribute, raise_on_error=True)

        if schema_attr is None:
            raise ValueError(f"Unable to find attribute {attribute}")

        return node_kind, schema_attr

    async def _mutate_enum_attribute(
        self,
        mutation: EnumMutation,
        kind: Union[str, InfrahubNodeTypes],
        attribute: str,
        option: Union[str, int],
        branch: Optional[str] = None,
    ) -> None:
        node_kind, schema_attr = await self._get_kind_and_attribute_schema(
            kind=kind, attribute=attribute, branch=branch
        )

        if schema_attr.enum is None:
            raise ValueError(f"Attribute '{schema_attr.name}' is not of kind Enum")

        input_data = {"data": {"kind": node_kind, "attribute": schema_attr.name, "enum": option}}

        query = Mutation(mutation=mutation.value, input_data=input_data, query={"ok": None})
        await self.client.execute_graphql(
            query=query.render(), branch_name=branch, tracker=f"mutation-{mutation.name}-add", timeout=60
        )

    async def add_enum_option(
        self, kind: Union[str, InfrahubNodeTypes], attribute: str, option: Union[str, int], branch: Optional[str] = None
    ) -> None:
        await self._mutate_enum_attribute(
            mutation=EnumMutation.add, kind=kind, attribute=attribute, option=option, branch=branch
        )

    async def remove_enum_option(
        self, kind: Union[str, InfrahubNodeTypes], attribute: str, option: Union[str, int], branch: Optional[str] = None
    ) -> None:
        await self._mutate_enum_attribute(
            mutation=EnumMutation.remove, kind=kind, attribute=attribute, option=option, branch=branch
        )

    async def _mutate_dropdown_attribute(
        self,
        mutation: DropdownMutation,
        kind: Union[str, InfrahubNodeTypes],
        attribute: str,
        option: str,
        branch: Optional[str] = None,
        dropdown_optional_args: Optional[DropdownMutationOptionalArgs] = None,
    ) -> None:
        dropdown_optional_args = dropdown_optional_args or DropdownMutationOptionalArgs(
            color="", description="", label=""
        )

        node_kind, schema_attr = await self._get_kind_and_attribute_schema(
            kind=kind, attribute=attribute, branch=branch
        )

        if schema_attr.kind != "Dropdown":
            raise ValueError(f"Attribute '{schema_attr.name}' is not of kind Dropdown")

        input_data: Dict[str, Any] = {
            "data": {
                "kind": node_kind,
                "attribute": schema_attr.name,
                "dropdown": option,
            }
        }
        if mutation == DropdownMutation.add:
            input_data["data"].update(dropdown_optional_args)

        query = Mutation(mutation=mutation.value, input_data=input_data, query={"ok": None})
        await self.client.execute_graphql(
            query=query.render(), branch_name=branch, tracker=f"mutation-{mutation.name}-remove", timeout=60
        )

    async def remove_dropdown_option(
        self, kind: Union[str, InfrahubNodeTypes], attribute: str, option: str, branch: Optional[str] = None
    ) -> None:
        await self._mutate_dropdown_attribute(
            mutation=DropdownMutation.remove, kind=kind, attribute=attribute, option=option, branch=branch
        )

    async def add_dropdown_option(
        self,
        kind: Union[str, InfrahubNodeTypes],
        attribute: str,
        option: str,
        color: Optional[str] = "",
        description: Optional[str] = "",
        label: Optional[str] = "",
        branch: Optional[str] = None,
    ) -> None:
        dropdown_optional_args = DropdownMutationOptionalArgs(color=color, description=description, label=label)
        await self._mutate_dropdown_attribute(
            mutation=DropdownMutation.add,
            kind=kind,
            attribute=attribute,
            option=option,
            branch=branch,
            dropdown_optional_args=dropdown_optional_args,
        )

    async def fetch(
        self, branch: str, namespaces: Optional[List[str]] = None
    ) -> MutableMapping[str, Union[NodeSchema, GenericSchema]]:
        """Fetch the schema from the server for a given branch.

        Args:
            branch (str): Name of the branch to fetch the schema for.

        Returns:
            Dict[str, NodeSchema]: Dictionnary of all schema organized by kind
        """
        url_parts = [("branch", branch)]
        if namespaces:
            url_parts.extend([("namespaces", ns) for ns in namespaces])
        query_params = urlencode(url_parts)
        url = f"{self.client.address}/api/schema/?{query_params}"

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
        self, branch: Optional[str] = None, refresh: bool = False, namespaces: Optional[List[str]] = None
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
            self.cache[branch] = self.fetch(branch=branch, namespaces=namespaces)

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

    def _get_kind_and_attribute_schema(
        self, kind: Union[str, InfrahubNodeTypes], attribute: str, branch: Optional[str] = None
    ) -> Tuple[str, AttributeSchema]:
        node_kind: str = kind._schema.kind if not isinstance(kind, str) else kind
        node_schema = self.client.schema.get(kind=node_kind, branch=branch)
        schema_attr = node_schema.get_attribute(attribute, raise_on_error=True)

        if schema_attr is None:
            raise ValueError(f"Unable to find attribute {attribute}")

        return node_kind, schema_attr

    def _mutate_enum_attribute(
        self,
        mutation: EnumMutation,
        kind: Union[str, InfrahubNodeTypes],
        attribute: str,
        option: Union[str, int],
        branch: Optional[str] = None,
    ) -> None:
        node_kind, schema_attr = self._get_kind_and_attribute_schema(kind=kind, attribute=attribute, branch=branch)

        if schema_attr.enum is None:
            raise ValueError(f"Attribute '{schema_attr.name}' is not of kind Enum")

        input_data = {"data": {"kind": node_kind, "attribute": schema_attr.name, "enum": option}}

        query = Mutation(mutation=mutation.value, input_data=input_data, query={"ok": None})
        self.client.execute_graphql(
            query=query.render(), branch_name=branch, tracker=f"mutation-{mutation.name}-add", timeout=60
        )

    def add_enum_option(
        self, kind: Union[str, InfrahubNodeTypes], attribute: str, option: Union[str, int], branch: Optional[str] = None
    ) -> None:
        self._mutate_enum_attribute(
            mutation=EnumMutation.add, kind=kind, attribute=attribute, option=option, branch=branch
        )

    def remove_enum_option(
        self, kind: Union[str, InfrahubNodeTypes], attribute: str, option: Union[str, int], branch: Optional[str] = None
    ) -> None:
        self._mutate_enum_attribute(
            mutation=EnumMutation.remove, kind=kind, attribute=attribute, option=option, branch=branch
        )

    def _mutate_dropdown_attribute(
        self,
        mutation: DropdownMutation,
        kind: Union[str, InfrahubNodeTypes],
        attribute: str,
        option: str,
        branch: Optional[str] = None,
        dropdown_optional_args: Optional[DropdownMutationOptionalArgs] = None,
    ) -> None:
        dropdown_optional_args = dropdown_optional_args or DropdownMutationOptionalArgs(
            color="", description="", label=""
        )
        node_kind, schema_attr = self._get_kind_and_attribute_schema(kind=kind, attribute=attribute, branch=branch)

        if schema_attr.kind != "Dropdown":
            raise ValueError(f"Attribute '{schema_attr.name}' is not of kind Dropdown")

        input_data: Dict[str, Any] = {
            "data": {
                "kind": node_kind,
                "attribute": schema_attr.name,
                "dropdown": option,
            }
        }

        if mutation == DropdownMutation.add:
            input_data["data"].update(dropdown_optional_args)

        query = Mutation(mutation=mutation.value, input_data=input_data, query={"ok": None})
        self.client.execute_graphql(
            query=query.render(), branch_name=branch, tracker=f"mutation-{mutation.name}-remove", timeout=60
        )

    def remove_dropdown_option(
        self, kind: Union[str, InfrahubNodeTypes], attribute: str, option: str, branch: Optional[str] = None
    ) -> None:
        self._mutate_dropdown_attribute(
            mutation=DropdownMutation.remove, kind=kind, attribute=attribute, option=option, branch=branch
        )

    def add_dropdown_option(
        self,
        kind: Union[str, InfrahubNodeTypes],
        attribute: str,
        option: str,
        color: Optional[str] = "",
        description: Optional[str] = "",
        label: Optional[str] = "",
        branch: Optional[str] = None,
    ) -> None:
        dropdown_optional_args = DropdownMutationOptionalArgs(color=color, description=description, label=label)
        self._mutate_dropdown_attribute(
            mutation=DropdownMutation.add,
            kind=kind,
            attribute=attribute,
            option=option,
            branch=branch,
            dropdown_optional_args=dropdown_optional_args,
        )

    def fetch(
        self, branch: str, namespaces: Optional[List[str]] = None
    ) -> MutableMapping[str, Union[NodeSchema, GenericSchema]]:
        """Fetch the schema from the server for a given branch.

        Args:
            branch (str): Name of the branch to fetch the schema for.

        Returns:
            Dict[str, NodeSchema]: Dictionnary of all schema organized by kind
        """
        url_parts = [("branch", branch)]
        if namespaces:
            url_parts.extend([("namespaces", ns) for ns in namespaces])
        query_params = urlencode(url_parts)
        url = f"{self.client.address}/api/schema/?{query_params}"

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
