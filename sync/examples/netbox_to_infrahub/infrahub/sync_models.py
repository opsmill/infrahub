from typing import Any, List, Optional

from infrahub_sync.adapters.infrahub import InfrahubModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------

class CoreStandardGroup(InfrahubModel):
    _modelname = "CoreStandardGroup"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class BuiltinTag(InfrahubModel):
    _modelname = "BuiltinTag"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class BuiltinLocation(InfrahubModel):
    _modelname = "BuiltinLocation"
    _identifiers = ("name",)
    _attributes = ("organization", "tags", "group", "description", "type")
    name: str
    description: Optional[str] = None
    type: str
    organization: Optional[str] = None
    tags: Optional[List[str]] = []
    group: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class BuiltinRole(InfrahubModel):
    _modelname = "BuiltinRole"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraRack(InfrahubModel):
    _modelname = "InfraRack"
    _identifiers = ("name", "location")
    _attributes = ("role", "tags", "height", "facility_id", "serial_number", "asset_tag")
    name: str
    height: int
    facility_id: Optional[str] = None
    serial_number: Optional[str] = None
    asset_tag: Optional[str] = None
    location: str
    role: Optional[str] = None
    tags: Optional[List[str]] = []
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class OrganizationGeneric(InfrahubModel):
    _modelname = "OrganizationGeneric"
    _identifiers = ("name",)
    _attributes = ("group", "description")
    name: str
    description: Optional[str] = None
    group: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None