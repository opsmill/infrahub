from typing import Any, List, Optional

from infrahub_sync.adapters.netbox import NetboxModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------


class InfraRack(NetboxModel):
    _modelname = "InfraRack"
    _identifiers = ("location", "name")
    _attributes = ("role", "tags", "description", "height", "facility_id", "serial_number")

    name: str
    description: Optional[str]
    height: str
    facility_id: Optional[str]
    serial_number: Optional[str]
    location: str
    role: Optional[str]
    tags: List[str] = []

    local_id: Optional[str]
    local_data: Optional[Any]


class BuiltinRole(NetboxModel):
    _modelname = "BuiltinRole"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]


class BuiltinLocation(NetboxModel):
    _modelname = "BuiltinLocation"
    _identifiers = ("name",)
    _attributes = ("description", "type")

    name: str
    description: Optional[str]
    type: str

    local_id: Optional[str]
    local_data: Optional[Any]


class BuiltinTag(NetboxModel):
    _modelname = "BuiltinTag"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]
