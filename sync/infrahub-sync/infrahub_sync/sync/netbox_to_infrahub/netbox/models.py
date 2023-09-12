from typing import Any, List, Optional

from infrahub_sync.adapters.netbox import NetboxModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------


class BuiltinTag(NetboxModel):
    _modelname = "BuiltinTag"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: Optional[str]

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
    _attributes = ("tags", "description", "type")

    name: str
    description: Optional[str]
    type: str
    tags: List[str] = []

    local_id: Optional[str]
    local_data: Optional[Any]


class InfraCircuit(NetboxModel):
    _modelname = "InfraCircuit"
    _identifiers = ("circuit_id",)
    _attributes = ("provider", "type", "tags", "description", "vendor_id")

    circuit_id: str
    description: Optional[str]
    vendor_id: Optional[str]
    provider: str
    type: str
    tags: List[str] = []

    local_id: Optional[str]
    local_data: Optional[Any]


class TemplateCircuitType(NetboxModel):
    _modelname = "TemplateCircuitType"
    _identifiers = ("name",)
    _attributes = ("tags", "description")

    name: str
    description: Optional[str]
    tags: List[str] = []

    local_id: Optional[str]
    local_data: Optional[Any]


class TemplateDeviceType(NetboxModel):
    _modelname = "TemplateDeviceType"
    _identifiers = ("name",)
    _attributes = ("manufacturer", "tags", "part_number", "description")

    part_number: Optional[str]
    name: str
    description: Optional[str]
    manufacturer: str
    tags: List[str] = []

    local_id: Optional[str]
    local_data: Optional[Any]


class InfraProviderNetwork(NetboxModel):
    _modelname = "InfraProviderNetwork"
    _identifiers = ("name",)
    _attributes = ("provider", "tags", "description", "vendor_id")

    name: str
    description: Optional[str]
    vendor_id: Optional[str]
    provider: str
    tags: List[str] = []

    local_id: Optional[str]
    local_data: Optional[Any]


class InfraRack(NetboxModel):
    _modelname = "InfraRack"
    _identifiers = ("location", "name")
    _attributes = ("role", "tags", "description", "height", "facility_id", "serial_number", "asset_tag")

    name: str
    description: Optional[str]
    height: str
    facility_id: Optional[str]
    serial_number: Optional[str]
    asset_tag: Optional[str]
    location: str
    role: Optional[str]
    tags: List[str] = []

    local_id: Optional[str]
    local_data: Optional[Any]


class OrgaProvider(NetboxModel):
    _modelname = "OrgaProvider"
    _identifiers = ("name",)
    _attributes = ("tags", "description")

    name: str
    description: Optional[str]
    tags: List[str] = []

    local_id: Optional[str]
    local_data: Optional[Any]
