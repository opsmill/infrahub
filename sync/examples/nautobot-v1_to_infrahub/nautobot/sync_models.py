from typing import Any, List, Optional

from infrahub_sync.adapters.nautobot import NautobotModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------

class CoreStandardGroup(NautobotModel):
    _modelname = "CoreStandardGroup"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class BuiltinTag(NautobotModel):
    _modelname = "BuiltinTag"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraAutonomousSystem(NautobotModel):
    _modelname = "InfraAutonomousSystem"
    _identifiers = ("name",)
    _attributes = ("organization", "description")
    name: str
    asn: int
    description: Optional[str]
    organization: str
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraCircuit(NautobotModel):
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

class TemplateCircuitType(NautobotModel):
    _modelname = "TemplateCircuitType"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraDevice(NautobotModel):
    _modelname = "InfraDevice"
    _identifiers = ("location", "organization", "name")
    _attributes = ("model", "rack", "role", "tags", "platform", "serial_number", "asset_tag")
    name: Optional[str]
    serial_number: Optional[str]
    asset_tag: Optional[str]
    location: str
    model: str
    rack: Optional[str]
    role: Optional[str]
    tags: List[str] = []
    platform: Optional[str]
    organization: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class TemplateDeviceType(NautobotModel):
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

class InfraFrontPort(NautobotModel):
    _modelname = "InfraFrontPort"
    _identifiers = ("name", "device")
    _attributes = ("rear_port", "description", "port_type")
    name: str
    description: Optional[str]
    port_type: Optional[str]
    rear_port: List[str] = []
    device: str
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraInterfaceL2L3(NautobotModel):
    _modelname = "InfraInterfaceL2L3"
    _identifiers = ("name", "device")
    _attributes = ("tagged_vlan", "tags", "l2_mode", "description", "mgmt_only", "mac_address", "interface_type")
    l2_mode: Optional[str]
    name: str
    description: Optional[str]
    mgmt_only: Optional[bool]
    mac_address: Optional[str]
    interface_type: Optional[str]
    untagged_vlan: Optional[str]
    tagged_vlan: List[str] = []
    device: str
    tags: List[str] = []
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraIPAddress(NautobotModel):
    _modelname = "InfraIPAddress"
    _identifiers = ("address", "vrf")
    _attributes = ("organization", "role", "description")
    address: str
    description: Optional[str]
    organization: Optional[str]
    vrf: Optional[str]
    role: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class TemplateLocationType(NautobotModel):
    _modelname = "TemplateLocationType"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraPlatform(NautobotModel):
    _modelname = "InfraPlatform"
    _identifiers = ("name", "manufacturer")
    _attributes = ("description", "napalm_driver")
    name: str
    description: Optional[str]
    napalm_driver: Optional[str]
    manufacturer: str
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraProviderNetwork(NautobotModel):
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

class InfraPrefix(NautobotModel):
    _modelname = "InfraPrefix"
    _identifiers = ("prefix", "vrf", "organization")
    _attributes = ("location", "role", "vlan", "description")
    prefix: str
    description: Optional[str]
    organization: Optional[str]
    location: Optional[str]
    role: Optional[str]
    vrf: Optional[str]
    vlan: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraRack(NautobotModel):
    _modelname = "InfraRack"
    _identifiers = ("name",)
    _attributes = ("location", "role", "tags", "height", "facility_id", "serial_number", "asset_tag")
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

class InfraRearPort(NautobotModel):
    _modelname = "InfraRearPort"
    _identifiers = ("name", "device")
    _attributes = ("description", "port_type")
    name: str
    description: Optional[str]
    port_type: Optional[str]
    device: str
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraRouteTarget(NautobotModel):
    _modelname = "InfraRouteTarget"
    _identifiers = ("name", "organization")
    _attributes = ("description",)
    name: str
    description: Optional[str]
    organization: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraVLAN(NautobotModel):
    _modelname = "InfraVLAN"
    _identifiers = ("name", "vlan_id", "location", "organization")
    _attributes = ("role", "vlan_group", "description")
    name: str
    description: Optional[str]
    vlan_id: int
    organization: Optional[str]
    location: Optional[str]
    role: Optional[str]
    vlan_group: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraVRF(NautobotModel):
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

class CoreOrganization(NautobotModel):
    _modelname = "CoreOrganization"
    _identifiers = ("name",)
    _attributes = ("group", "description", "type")
    name: str
    description: Optional[str]
    type: Optional[str]
    group: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class BuiltinStatus(NautobotModel):
    _modelname = "BuiltinStatus"
    _identifiers = ("name",)
    _attributes = ("label", "description")
    name: str
    label: Optional[str]
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
    _attributes = ("organization", "location_type", "description", "type")
    name: str
    description: Optional[str]
    type: str
    organization: Optional[str]
    location_type: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]