from typing import Any, Optional

from pydantic import BaseModel, Field

from infrahub.core.constants import PathResourceType, PathType


class InfrahubPath(BaseModel):
    """A Path represent the location of a single resource stored in Infrahub.
    TODO Add definition of a resource
    """

    resource_type: PathResourceType = Field(PathResourceType.DATA, description="Indicate the type of the resource")
    node_id: str = Field(..., description="UUID of the node")
    path_type: PathType
    kind: str = Field(..., description="Kind of the main node")
    field_name: Optional[str] = Field(None, description="Name of the field (either an attribute or a relationship)")
    property_name: Optional[str] = Field(None, description="Name of the property")
    peer_id: Optional[str] = Field(None, description="")
    value: Optional[Any] = Field(None, description="Optional value of the resource")

    def __hash__(self) -> int:
        return hash((type(self),) + tuple(self.__dict__.values()))

    def _path(self, with_peer: bool = True) -> str:
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

    def __str__(self) -> str:
        return self._path()

    # @property
    # def change_type(self) -> str:
    #     if self.path_type in [PathType.ATTRIBUTE, PathType.RELATIONSHIP_MANY, PathType.RELATIONSHIP_ONE]:
    #         if self.property_name and self.property_name != "HAS_VALUE":
    #             return f"{self.path_type.value}_property"
    #         return f"{self.path_type.value}_value"
    #     return self.path_type.value
