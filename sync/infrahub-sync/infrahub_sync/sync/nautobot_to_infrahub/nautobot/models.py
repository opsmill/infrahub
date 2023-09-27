from typing import Any, List, Optional

from infrahub_sync.adapters.nautobot import NautobotModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------


class BuiltinTag(NautobotModel):
    _modelname = "BuiltinTag"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]


class BuiltinRole(NautobotModel):
    _modelname = "BuiltinRole"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]


class BuiltinLocation(NautobotModel):
    _modelname = "BuiltinLocation"
    _identifiers = ("name",)
    _attributes = ("description", "type")

    name: str
    description: Optional[str]
    type: str

    local_id: Optional[str]
    local_data: Optional[Any]


class InfraRack(NautobotModel):
    _modelname = "InfraRack"
    _identifiers = ("location", "name")
    _attributes = ("role", "tags", "height", "facility_id", "serial_number")

    name: str
    height: str
    facility_id: Optional[str]
    serial_number: Optional[str]
    location: str
    role: Optional[str]
    tags: List[str] = []

    local_id: Optional[str]
    local_data: Optional[Any]
