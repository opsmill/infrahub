from typing import Any, List, Optional

from infrahub_sync.adapters.infrahub import InfrahubModel


class Tag(InfrahubModel):
    _modelname = "tag"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]


class Role(InfrahubModel):
    _modelname = "role"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]


class Rack(InfrahubModel):
    _modelname = "rack"
    _identifiers = ("location", "name")
    _attributes = ("tags", "description", "height")

    name: str
    description: Optional[str]
    height: str
    location: str
    tags: List[str] = []

    local_id: Optional[str]
    local_data: Optional[Any]


class Location(InfrahubModel):
    _modelname = "location"
    _identifiers = ("name",)
    _attributes = ("description", "type")

    name: str
    description: Optional[str]
    type: str

    local_id: Optional[str]
    local_data: Optional[Any]
