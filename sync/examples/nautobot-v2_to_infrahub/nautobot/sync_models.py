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
    description: Optional[str]
    name: str
    asn: int
    organization: str
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraCircuit(NautobotModel):
    _modelname = "InfraCircuit"
    _identifiers = ("circuit_id",)
    _attributes = ("provider", "type", "tags", "description", "vendor_id")
    description: Optional[str]
    vendor_id: Optional[str]
    circuit_id: str
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
    _attributes = ("role", "rack", "platform", "model", "tags", "serial_number", "asset_tag")
    serial_number: Optional[str]
    asset_tag: Optional[str]
    name: Optional[str]
    role: Optional[str]
    rack: Optional[str]
    platform: Optional[str]
    model: str
    tags: List[str] = []
    location: str
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
    _identifiers = ("address", "prefix")
    _attributes = ("organization", "role", "interfaces", "description")
    description: Optional[str]
    address: str
    prefix: Optional[str]
    organization: Optional[str]
    role: Optional[str]
    interfaces: List[str] = []
    local_id: Optional[str]
    local_data: Optional[Any]

class TemplateLocationType(NautobotModel):
    _modelname = "TemplateLocationType"
    _identifiers = ("name",)
    _attributes = ("description",)
    description: Optional[str]
    name: str
    local_id: Optional[str]
    local_data: Optional[Any]

class NautobotNamespace(NautobotModel):
    _modelname = "NautobotNamespace"
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
    description: Optional[str]
    name: str
    napalm_driver: Optional[str]
    manufacturer: str
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraProviderNetwork(NautobotModel):
    _modelname = "InfraProviderNetwork"
    _identifiers = ("name",)
    _attributes = ("provider", "tags", "description", "vendor_id")
    description: Optional[str]
    name: str
    vendor_id: Optional[str]
    provider: str
    tags: List[str] = []
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraPrefix(NautobotModel):
    _modelname = "InfraPrefix"
    _identifiers = ("prefix", "namespace")
    _attributes = ("vlan", "location", "organization", "role", "description")
    prefix: str
    description: Optional[str]
    vlan: Optional[str]
    namespace: Optional[str]
    location: Optional[str]
    organization: Optional[str]
    role: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraRack(NautobotModel):
    _modelname = "InfraRack"
    _identifiers = ("name",)
    _attributes = ("role", "tags", "location", "serial_number", "height", "asset_tag", "facility_id")
    serial_number: Optional[str]
    name: str
    height: str
    asset_tag: Optional[str]
    facility_id: Optional[str]
    role: Optional[str]
    tags: List[str] = []
    location: str
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
    vlan_id: int
    name: str
    description: Optional[str]
    location: Optional[str]
    role: Optional[str]
    organization: Optional[str]
    vlan_group: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class InfraVRF(NautobotModel):
    _modelname = "InfraVRF"
    _identifiers = ("name", "namespace")
    _attributes = ("export_rt", "import_rt", "organization", "vrf_rd", "description")
    vrf_rd: Optional[str]
    name: str
    description: Optional[str]
    export_rt: List[str] = []
    import_rt: List[str] = []
    organization: Optional[str]
    namespace: Optional[str]
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

class BuiltinRole(NautobotModel):
    _modelname = "BuiltinRole"
    _identifiers = ("name",)
    _attributes = ("label", "description")
    name: str
    label: Optional[str]
    description: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]

class BuiltinLocation(NautobotModel):
    _modelname = "BuiltinLocation"
    _identifiers = ("name",)
    _attributes = ("tags", "location_type", "description", "type")
    name: str
    description: Optional[str]
    type: str
    tags: List[str] = []
    location_type: Optional[str]
    local_id: Optional[str]
    local_data: Optional[Any]