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
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class BuiltinTag(NetboxModel):
    _modelname = "BuiltinTag"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraCircuit(NetboxModel):
    _modelname = "InfraCircuit"
    _identifiers = ("circuit_id",)
    _attributes = ("provider", "type", "tags", "description", "vendor_id")
    circuit_id: str
    description: Optional[str] = None
    vendor_id: Optional[str] = None
    provider: str
    type: str
    tags: Optional[List[str]] = []
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraDevice(NetboxModel):
    _modelname = "InfraDevice"
    _identifiers = ("name", "location", "rack", "organization")
    _attributes = ("model", "role", "tags", "description", "serial_number", "asset_tag")
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
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraIPAddress(NetboxModel):
    _modelname = "InfraIPAddress"
    _identifiers = ("address", "vrf")
    _attributes = ("organization", "description")
    address: str
    description: Optional[str] = None
    organization: Optional[str] = None
    vrf: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraInterfaceL2L3(NetboxModel):
    _modelname = "InfraInterfaceL2L3"
    _identifiers = ("name", "device")
    _attributes = ("tagged_vlan", "tags", "l2_mode", "description", "mgmt_only", "mac_address", "interface_type")
    l2_mode: Optional[str] = None
    name: str
    description: Optional[str] = None
    mgmt_only: Optional[bool] = False
    mac_address: Optional[str] = None
    interface_type: Optional[str] = None
    untagged_vlan: Optional[str] = None
    tagged_vlan: Optional[List[str]] = []
    device: str
    tags: Optional[List[str]] = []
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraPrefix(NetboxModel):
    _modelname = "InfraPrefix"
    _identifiers = ("prefix", "vrf")
    _attributes = ("organization", "location", "role", "description")
    prefix: str
    description: Optional[str] = None
    organization: Optional[str] = None
    location: Optional[str] = None
    role: Optional[str] = None
    vrf: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraProviderNetwork(NetboxModel):
    _modelname = "InfraProviderNetwork"
    _identifiers = ("name",)
    _attributes = ("provider", "tags", "description", "vendor_id")
    name: str
    description: Optional[str] = None
    vendor_id: Optional[str] = None
    provider: str
    tags: Optional[List[str]] = []
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraRack(NetboxModel):
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

class InfraRouteTarget(NetboxModel):
    _modelname = "InfraRouteTarget"
    _identifiers = ("name", "organization")
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    organization: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraVLAN(NetboxModel):
    _modelname = "InfraVLAN"
    _identifiers = ("name", "vlan_id", "location", "vlan_group")
    _attributes = ("organization", "description")
    name: str
    description: Optional[str] = None
    vlan_id: int
    organization: Optional[str] = None
    location: Optional[str] = None
    vlan_group: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraVRF(NetboxModel):
    _modelname = "InfraVRF"
    _identifiers = ("name",)
    _attributes = ("organization", "import_rt", "export_rt", "description", "vrf_rd")
    name: str
    description: Optional[str] = None
    vrf_rd: Optional[str] = None
    organization: Optional[str] = None
    import_rt: Optional[List[str]] = []
    export_rt: Optional[List[str]] = []
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class LocationGeneric(NetboxModel):
    _modelname = "LocationGeneric"
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

class OrganizationGeneric(NetboxModel):
    _modelname = "OrganizationGeneric"
    _identifiers = ("name",)
    _attributes = ("group", "description")
    name: str
    description: Optional[str] = None
    group: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class RoleGeneric(NetboxModel):
    _modelname = "RoleGeneric"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class TemplateCircuitType(NetboxModel):
    _modelname = "TemplateCircuitType"
    _identifiers = ("name",)
    _attributes = ("tags", "description")
    name: str
    description: Optional[str] = None
    tags: Optional[List[str]] = []
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class TemplateDeviceType(NetboxModel):
    _modelname = "TemplateDeviceType"
    _identifiers = ("name", "manufacturer")
    _attributes = ("tags", "part_number", "height", "full_depth")
    part_number: Optional[str] = None
    height: Optional[int] = None
    full_depth: Optional[bool] = None
    name: str
    manufacturer: str
    tags: Optional[List[str]] = []
    local_id: Optional[str] = None
    local_data: Optional[Any] = None