from typing import Optional, Any

from infrahub_sync.adapters.infrahub import InfrahubModel

class Tag(InfrahubModel):

    _modelname = "tag"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: Optional[Optional[Optional[str]]]

    local_id: Optional[str]
    local_data: Optional[Any]

class Location(InfrahubModel):

    _modelname = "location"
    _identifiers = ("name",)
    _attributes = ("description", "type")

    name: str
    description: Optional[Optional[Optional[str]]]
    type: str

    local_id: Optional[str]
    local_data: Optional[Any]

class Role(InfrahubModel):

    _modelname = "role"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: Optional[Optional[Optional[str]]]

    local_id: Optional[str]
    local_data: Optional[Any]

