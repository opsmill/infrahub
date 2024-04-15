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

class InfraAutonomousSystem(InfrahubModel):
    _modelname = "InfraAutonomousSystem"
    _identifiers = ("name",)
    _attributes = ("organization", "description")
    name: str
    asn: int
    description: Optional[str] = None
    organization: str
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraCircuit(InfrahubModel):
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

class InfraDevice(InfrahubModel):
    _modelname = "InfraDevice"
    _identifiers = ("location", "organization", "name")
    _attributes = ("model", "rack", "role", "tags", "platform", "serial_number", "asset_tag")
    name: Optional[str] = None
    serial_number: Optional[str] = None
    asset_tag: Optional[str] = None
    location: str
    model: str
    rack: Optional[str] = None
    role: Optional[str] = None
    tags: Optional[List[str]] = []
    platform: Optional[str] = None
    organization: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraFrontPort(InfrahubModel):
    _modelname = "InfraFrontPort"
    _identifiers = ("name", "device")
    _attributes = ("rear_port", "description", "port_type")
    name: str
    description: Optional[str] = None
    port_type: Optional[str] = None
    rear_port: Optional[List[str]] = []
    device: str
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraIPAddress(InfrahubModel):
    _modelname = "InfraIPAddress"
    _identifiers = ("address", "vrf")
    _attributes = ("organization", "role", "description")
    address: str
    description: Optional[str] = None
    organization: Optional[str] = None
    vrf: Optional[str] = None
    role: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraInterfaceL2L3(InfrahubModel):
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

class InfraPlatform(InfrahubModel):
    _modelname = "InfraPlatform"
    _identifiers = ("name", "manufacturer")
    _attributes = ("description", "napalm_driver")
    name: str
    description: Optional[str] = None
    napalm_driver: Optional[str] = None
    manufacturer: str
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraPrefix(InfrahubModel):
    _modelname = "InfraPrefix"
    _identifiers = ("prefix", "vrf", "organization")
    _attributes = ("role", "vlan", "description")
    prefix: str
    description: Optional[str] = None
    organization: Optional[str] = None
    role: Optional[str] = None
    vrf: Optional[str] = None
    vlan: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraProviderNetwork(InfrahubModel):
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

class InfraRack(InfrahubModel):
    _modelname = "InfraRack"
    _identifiers = ("name",)
    _attributes = ("location", "role", "tags", "height", "facility_id", "serial_number", "asset_tag")
    name: str
    height: Optional[int] = None
    facility_id: Optional[str] = None
    serial_number: Optional[str] = None
    asset_tag: Optional[str] = None
    location: str
    role: Optional[str] = None
    tags: Optional[List[str]] = []
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraRearPort(InfrahubModel):
    _modelname = "InfraRearPort"
    _identifiers = ("name", "device")
    _attributes = ("description", "port_type")
    name: str
    description: Optional[str] = None
    port_type: Optional[str] = None
    device: str
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraRouteTarget(InfrahubModel):
    _modelname = "InfraRouteTarget"
    _identifiers = ("name", "organization")
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    organization: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraVLAN(InfrahubModel):
    _modelname = "InfraVLAN"
    _identifiers = ("name", "vlan_id", "location", "organization")
    _attributes = ("role", "vlan_group", "description")
    name: str
    description: Optional[str] = None
    vlan_id: int
    organization: Optional[str] = None
    role: Optional[str] = None
    vlan_group: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraVRF(InfrahubModel):
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

class LocationGeneric(InfrahubModel):
    _modelname = "LocationGeneric"
    _identifiers = ("name",)
    _attributes = ("organization", "location_type", "description", "type")
    name: str
    description: Optional[str] = None
    type: str
    organization: Optional[str] = None
    location_type: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class RoleGeneric(InfrahubModel):
    _modelname = "RoleGeneric"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class StatusGeneric(InfrahubModel):
    _modelname = "StatusGeneric"
    _identifiers = ("name",)
    _attributes = ("label", "description")
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class TemplateCircuitType(InfrahubModel):
    _modelname = "TemplateCircuitType"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class TemplateDeviceType(InfrahubModel):
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

class TemplateLocationType(InfrahubModel):
    _modelname = "TemplateLocationType"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None