from typing import Optional, Any, List

from infrahub_sync.adapters.netbox import NetboxModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------

class Tag(NetboxModel):

    _modelname = "tag"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]

class Role(NetboxModel):

    _modelname = "role"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]

class Rack(NetboxModel):

    _modelname = "rack"
    _identifiers = ("location", "name")
    _attributes = ("tags", "description", "height", "serial_number")

    name: str
    description: Optional[str]
    height: str
    serial_number: Optional[str]
    location: str
    tags: List[str] = []

    local_id: Optional[str]
    local_data: Optional[Any]

class Location(NetboxModel):

    _modelname = "location"
    _identifiers = ("name",)
    _attributes = ("description", "type")

    name: str
    description: Optional[str]
    type: str

    local_id: Optional[str]
    local_data: Optional[Any]

