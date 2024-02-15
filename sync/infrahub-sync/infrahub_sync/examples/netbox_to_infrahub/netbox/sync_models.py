from typing import Any, List, Optional

from infrahub_sync.adapters.netbox import NetboxModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------

class CoreStandardGroup(NetboxModel):
    _modelname = "CoreStandardGroup"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str]
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

class InfraDevice(NetboxModel):
    _modelname = "InfraDevice"
    _identifiers = ("name", "location", "rack", "organization")
    _attributes = ("model", "role", "tags", "description", "serial_number", "asset_tag")
    name: Optional[str]
    description: Optional[str]
    serial_number: Optional[str]
    asset_tag: Optional[str]
    location: str
    model: str
    rack: Optional[str]
    role: Optional[str]
    tags: List[str] = []
    organization: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class TemplateDeviceType(NetboxModel):
    _modelname = "TemplateDeviceType"
    _identifiers = ("name", "manufacturer")
    _attributes = ("tags", "part_number", "height", "full_depth")
    part_number: Optional[str]
    height: Optional[int]
    full_depth: Optional[bool]
    name: str
    manufacturer: str
    tags: List[str] = []
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraIPAddress(NetboxModel):
    _modelname = "InfraIPAddress"
    _identifiers = ("address", "vrf")
    _attributes = ("organization", "description")
    address: str
    description: Optional[str]
    organization: Optional[str]
    vrf: Optional[str]
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

class InfraPrefix(NetboxModel):
    _modelname = "InfraPrefix"
    _identifiers = ("prefix", "vrf")
    _attributes = ("organization", "location", "role", "description")
    prefix: str
    description: Optional[str]
    organization: Optional[str]
    location: Optional[str]
    role: Optional[str]
    vrf: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraRack(NetboxModel):
    _modelname = "InfraRack"
    _identifiers = ("name", "location")
    _attributes = ("role", "tags", "height", "facility_id", "serial_number", "asset_tag")
    name: str
    height: str
    facility_id: Optional[str]
    serial_number: Optional[str]
    asset_tag: Optional[str]
    location: str
    role: Optional[str]
    tags: List[str] = []
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraRouteTarget(NetboxModel):
    _modelname = "InfraRouteTarget"
    _identifiers = ("name", "organization")
    _attributes = ("description",)
    name: str
    description: Optional[str]
    organization: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraVLAN(NetboxModel):
    _modelname = "InfraVLAN"
    _identifiers = ("name", "vlan_id", "location", "vlan_group")
    _attributes = ("organization", "description")
    name: str
    description: Optional[str]
    vlan_id: int
    organization: Optional[str]
    location: Optional[str]
    vlan_group: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraVRF(NetboxModel):
    _modelname = "InfraVRF"
    _identifiers = ("name",)
    _attributes = ("organization", "import_rt", "export_rt", "description", "vrf_rd")
    name: str
    description: Optional[str]
    vrf_rd: Optional[str]
    organization: Optional[str]
    import_rt: List[str] = []
    export_rt: List[str] = []
    local_id: Optional[str]
    local_data: Optional[Any]

class CoreOrganization(NetboxModel):
    _modelname = "CoreOrganization"
    _identifiers = ("name",)
    _attributes = ("group", "description", "type")
    name: str
    description: Optional[str]
    type: Optional[str]
    group: Optional[str]
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
    _attributes = ("organization", "tags", "group", "description", "type")
    name: str
    description: Optional[str]
    type: str
    organization: Optional[str]
    tags: List[str] = []
    group: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]