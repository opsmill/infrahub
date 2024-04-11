from typing import Any, List, Optional

from infrahub_sync.adapters.netbox import NetboxModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------

class CoreStandardGroup(NetboxModel):
    _modelname = "CoreStandardGroup"
    _identifiers: List[str] = ("name",)
    _attributes: List[str] = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str]
    local_data: Optional[Any] = None

class BuiltinTag(NetboxModel):
    _modelname = "BuiltinTag"
    _identifiers: List[str] = ("name",)
    _attributes: List[str] = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str]
    local_data: Optional[Any] = None

class BuiltinLocation(NetboxModel):
    _modelname = "BuiltinLocation"
    _identifiers: List[str] = ("name",)
    _attributes: List[str] = ("organization", "tags", "group", "description", "type")
    name: str
    description: Optional[str] = None
    type: str
    organization: Optional[str] = None
    tags: Optional[List[str]] = []
    group: Optional[str] = None
    local_id: Optional[str]
    local_data: Optional[Any] = None

class BuiltinRole(NetboxModel):
    _modelname = "BuiltinRole"
    _identifiers: List[str] = ("name",)
    _attributes: List[str] = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str]
    local_data: Optional[Any] = None

class InfraCircuit(NetboxModel):
    _modelname = "InfraCircuit"
    _identifiers: List[str] = ("name",)
    _attributes: List[str] = ("provider", "type", "tags", "description", "vendor_id")
    circuit_id: str
    description: Optional[str] = None
    vendor_id: Optional[str] = None
    provider: str
    type: str
    tags: Optional[List[str]] = []
    local_id: Optional[str]
    local_data: Optional[Any] = None

class InfraDevice(NetboxModel):
    _modelname = "InfraDevice"
    _identifiers: List[str] = ("name", "location", "rack", "organization")
    _attributes: List[str] = ("model", "role", "tags", "description", "serial_number", "asset_tag")
    name: Optional[str] = None
    description: Optional[str] = None
    serial_number: Optional[str] = None
    asset_tag: Optional[str] = None
    location: str
    model: str
    rack: Optional[str] = None
    role: Optional[str] = None
    tags: Optional[List[str]] = []
    organization: Optional[str] = None
    local_id: Optional[str]
    local_data: Optional[Any] = None

class InfraIPAddress(NetboxModel):
    _modelname = "InfraIPAddress"
    _identifiers: List[str] = ("address", "vrf")
    _attributes: List[str] = ("organization", "description")
    address: str
    description: Optional[str] = None
    organization: Optional[str] = None
    vrf: Optional[str] = None
    local_id: Optional[str]
    local_data: Optional[Any] = None

class InfraPrefix(NetboxModel):
    _modelname = "InfraPrefix"
    _identifiers: List[str] = ("prefix", "vrf")
    _attributes: List[str] = ("organization", "location", "role", "description")
    prefix: str
    description: Optional[str] = None
    organization: Optional[str] = None
    location: Optional[str] = None
    role: Optional[str] = None
    vrf: Optional[str] = None
    local_id: Optional[str]
    local_data: Optional[Any] = None

class InfraProviderNetwork(NetboxModel):
    _modelname = "InfraProviderNetwork"
    _identifiers: List[str] = ("name",)
    _attributes: List[str] = ("provider", "tags", "description", "vendor_id")
    name: str
    description: Optional[str] = None
    vendor_id: Optional[str] = None
    provider: str
    tags: Optional[List[str]] = []
    local_id: Optional[str]
    local_data: Optional[Any] = None

class InfraRack(NetboxModel):
    _modelname = "InfraRack"
    _identifiers: List[str] = ("name", "location")
    _attributes: List[str] = ("role", "tags", "height", "facility_id", "serial_number", "asset_tag")
    name: str
    height: str
    facility_id: Optional[str] = None
    serial_number: Optional[str] = None
    asset_tag: Optional[str] = None
    location: str
    role: Optional[str] = None
    tags: Optional[List[str]] = []
    local_id: Optional[str]
    local_data: Optional[Any] = None

class InfraRouteTarget(NetboxModel):
    _modelname = "InfraRouteTarget"
    _identifiers: List[str] = ("name", "organization")
    _attributes: List[str] = ("description",)
    name: str
    description: Optional[str] = None
    organization: Optional[str] = None
    local_id: Optional[str]
    local_data: Optional[Any] = None

class InfraVLAN(NetboxModel):
    _modelname = "InfraVLAN"
    _identifiers: List[str] = ("name", "vlan_id", "location", "vlan_group")
    _attributes: List[str] = ("organization", "description")
    name: str
    description: Optional[str] = None
    vlan_id: int
    organization: Optional[str] = None
    location: Optional[str] = None
    vlan_group: Optional[str] = None
    local_id: Optional[str]
    local_data: Optional[Any] = None

class InfraVRF(NetboxModel):
    _modelname = "InfraVRF"
    _identifiers: List[str] = ("name",)
    _attributes: List[str] = ("organization", "import_rt", "export_rt", "description", "vrf_rd")
    name: str
    description: Optional[str] = None
    vrf_rd: Optional[str] = None
    organization: Optional[str] = None
    import_rt: Optional[List[str]] = []
    export_rt: Optional[List[str]] = []
    local_id: Optional[str]
    local_data: Optional[Any] = None

class OrganizationGeneric(NetboxModel):
    _modelname = "OrganizationGeneric"
    _identifiers: List[str] = ("name",)
    _attributes: List[str] = ("group", "description")
    name: str
    description: Optional[str] = None
    group: Optional[str] = None
    local_id: Optional[str]
    local_data: Optional[Any] = None

class TemplateCircuitType(NetboxModel):
    _modelname = "TemplateCircuitType"
    _identifiers: List[str] = ("name",)
    _attributes: List[str] = ("tags", "description")
    name: str
    description: Optional[str] = None
    tags: Optional[List[str]] = []
    local_id: Optional[str]
    local_data: Optional[Any] = None

class TemplateDeviceType(NetboxModel):
    _modelname = "TemplateDeviceType"
    _identifiers: List[str] = ("name", "manufacturer")
    _attributes: List[str] = ("tags", "part_number", "height", "full_depth")
    part_number: Optional[str] = None
    height: Optional[int] = None
    full_depth: Optional[bool] = None
    name: str
    manufacturer: str
    tags: Optional[List[str]] = []
    local_id: Optional[str]
    local_data: Optional[Any] = None