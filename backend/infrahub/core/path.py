from __future__ import annotations

from collections import defaultdict
from itertools import chain
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field
from typing_extensions import Self

from infrahub.core.constants import PathResourceType, PathType, SchemaPathType

if TYPE_CHECKING:
    from infrahub.core.schema import GenericSchema, NodeSchema

# DataPath
#   Node
#   Attribute or a Relationship
#   A peer of a node
#   A value or a property
# SchemaPath
# FilePath


class InfrahubPath(BaseModel):
    """A Path represent the location of a single resource stored in Infrahub.
    TODO Add definition of a resource
    """

    def __hash__(self) -> int:
        return hash((type(self),) + tuple(self.__dict__.values()))

    def __str__(self) -> str:
        return self.get_path()

    def get_path(self) -> str:
        raise NotImplementedError()

    @property
    def resource_type(self) -> PathResourceType:
        raise NotImplementedError()

    # def from_string(self, value: str):
    #     raise NotImplementedError

    # @property
    # def change_type(self) -> str:
    #     if self.path_type in [PathType.ATTRIBUTE, PathType.RELATIONSHIP_MANY, PathType.RELATIONSHIP_ONE]:
    #         if self.property_name and self.property_name != "HAS_VALUE":
    #             return f"{self.path_type.value}_property"
    #         return f"{self.path_type.value}_value"
    #     return self.path_type.value


class DataPath(InfrahubPath):
    branch: str = Field(..., description="Name of the branch")
    path_type: PathType
    node_id: str = Field(..., description="Kind of the model in the schema")
    kind: str = Field(..., description="Kind of the main node")
    field_name: str | None = Field(
        default=None, description="Name of the field (either an attribute or a relationship)"
    )
    property_name: str | None = Field(default=None, description="Name of the property")
    peer_id: str | None = Field(default=None, description="")
    value: Any | None = Field(default=None, description="Optional value of the resource")

    @property
    def resource_type(self) -> PathResourceType:
        return PathResourceType.DATA

    def get_path(self, with_peer: bool = True) -> str:
        identifier = f"{self.resource_type.value}/{self.node_id}"
        if self.field_name:
            identifier += f"/{self.field_name}"

        if self.path_type == PathType.RELATIONSHIP_ONE and not self.property_name:
            identifier += "/peer"

        if with_peer and self.peer_id:
            identifier += f"/{self.peer_id}"

        if self.property_name and self.property_name == "HAS_VALUE":
            identifier += "/value"
        elif self.property_name:
            identifier += f"/property/{self.property_name}"

        return identifier


class GroupedDataPaths:
    def __init__(self) -> None:
        self._grouped_data_paths: dict[str, list[DataPath]] = defaultdict(list)

    def add_data_path(self, data_path: DataPath, grouping_key: str = "") -> None:
        self.add_data_paths([data_path], grouping_key)

    def add_data_paths(self, data_paths: list[DataPath], grouping_key: str = "") -> None:
        self._grouped_data_paths[grouping_key].extend(data_paths)

    def get_data_paths(self, grouping_key: str = "") -> list[DataPath]:
        return self._grouped_data_paths.get(grouping_key, [])

    def get_all_data_paths(self) -> list[DataPath]:
        return list(chain(*self._grouped_data_paths.values()))

    def get_grouping_keys(self) -> list[str]:
        return list(self._grouped_data_paths.keys())


class SchemaPath(InfrahubPath):
    path_type: SchemaPathType
    schema_kind: str = Field(..., description="Kind of the model in the schema")
    schema_id: str | None = Field(default=None, description="UUID of the model in the schema")
    field_name: str | None = Field(
        default=None, description="Name of the field (either an attribute or a relationship)"
    )
    property_name: str | None = Field(default=None, description="Name of the property")

    @property
    def resource_type(self) -> PathResourceType:
        return PathResourceType.SCHEMA

    def get_path(self) -> str:
        identifier = f"{self.resource_type.value}/{self.schema_kind}"

        if self.field_name:
            identifier += f"/{self.field_name}"

        if self.property_name and not self.path_type == SchemaPathType.NODE:
            identifier += f"/{self.property_name}"

        return identifier

    @classmethod
    def init(
        cls,
        schema: NodeSchema | GenericSchema,
        schema_id: str | None = None,
        field_name: str | None = None,
        property_name: str | None = None,
    ) -> Self:
        if field_name and not schema.get_field(name=field_name, raise_on_error=False):
            raise ValueError(f"Field : {field_name} is not valid for {schema.kind}")

        path_type = SchemaPathType.NODE
        if field_name:
            field = schema.get_field(name=field_name)
            path_type = SchemaPathType.ATTRIBUTE if field.is_attribute else SchemaPathType.RELATIONSHIP

        if field_name and property_name and not hasattr(schema.get_field(name=field_name), property_name):
            raise ValueError(f"Property {property_name} is not valid for {schema.kind}:{field_name}")

        return cls(
            schema_kind=schema.kind,
            path_type=path_type,
            schema_id=schema_id,
            field_name=field_name,
            property_name=property_name,
        )


class FilePath(InfrahubPath):
    repository_name: str = Field(..., description="name of the repository")

    @property
    def resource_type(self) -> PathResourceType:
        return PathResourceType.FILE

    def get_path(self) -> str:
        return f"{self.resource_type.value}/{self.repository_name}"
