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
    description: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]


class BuiltinTag(InfrahubModel):
    _modelname = "BuiltinTag"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]


class CoreOrganization(InfrahubModel):
    _modelname = "CoreOrganization"
    _identifiers = ("name",)
    _attributes = ("group", "description", "type")

    name: str
    description: Optional[str]
    type: Optional[str]
    group: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]


class BuiltinRole(InfrahubModel):
    _modelname = "BuiltinRole"
    _identifiers = ("name",)
    _attributes = ("label", "description")

    name: str
    label: Optional[str]
    description: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]


class BuiltinLocation(InfrahubModel):
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


class InfraAutonomousSystem(InfrahubModel):
    _modelname = "InfraAutonomousSystem"
    _identifiers = ("name",)
    _attributes = ("organization", "description")

    name: str
    asn: int
    description: Optional[str]
    organization: str

    local_id: Optional[str]
    local_data: Optional[Any]


class InfraCircuit(InfrahubModel):
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


class TemplateCircuitType(InfrahubModel):
    _modelname = "TemplateCircuitType"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]


class InfraDevice(InfrahubModel):
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


class TemplateDeviceType(InfrahubModel):
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


class InfraFrontPort(InfrahubModel):
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


class InfraInterfaceL2L3(InfrahubModel):
    _modelname = "InfraInterfaceL2L3"
    _identifiers = ("name", "device")
    _attributes = ("tags", "l2_mode", "description", "mgmt_only", "mac_address", "interface_type")

    l2_mode: Optional[str]
    name: str
    description: Optional[str]
    mgmt_only: Optional[bool]
    mac_address: Optional[str]
    interface_type: Optional[str]
    untagged_vlan: Optional[str]
    tagged_vlan: Optional[str]
    device: str
    tags: List[str] = []

    local_id: Optional[str]
    local_data: Optional[Any]


class InfraIPAddress(InfrahubModel):
    _modelname = "InfraIPAddress"
    _identifiers = ("address", "prefix")
    _attributes = ("organization", "interfaces", "role", "description")

    address: str
    description: Optional[str]
    organization: Optional[str]
    interfaces: List[str] = []
    prefix: Optional[str]
    role: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]


class TemplateLocationType(InfrahubModel):
    _modelname = "TemplateLocationType"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]


class NautobotNamespace(InfrahubModel):
    _modelname = "NautobotNamespace"
    _identifiers = ("name",)
    _attributes = ("description",)

    name: str
    description: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]


class InfraPlatform(InfrahubModel):
    _modelname = "InfraPlatform"
    _identifiers = ("name", "manufacturer")
    _attributes = ("description", "napalm_driver")

    name: str
    description: Optional[str]
    napalm_driver: Optional[str]
    manufacturer: str

    local_id: Optional[str]
    local_data: Optional[Any]


class InfraProviderNetwork(InfrahubModel):
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


class InfraPrefix(InfrahubModel):
    _modelname = "InfraPrefix"
    _identifiers = ("prefix", "namespace")
    _attributes = ("organization", "location", "role", "vlan", "description")

    prefix: str
    description: Optional[str]
    organization: Optional[str]
    namespace: Optional[str]
    location: Optional[str]
    role: Optional[str]
    vlan: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]


class InfraRack(InfrahubModel):
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


class InfraRearPort(InfrahubModel):
    _modelname = "InfraRearPort"
    _identifiers = ("name", "device")
    _attributes = ("description", "port_type")

    name: str
    description: Optional[str]
    port_type: Optional[str]
    device: str

    local_id: Optional[str]
    local_data: Optional[Any]


class InfraRouteTarget(InfrahubModel):
    _modelname = "InfraRouteTarget"
    _identifiers = ("name", "organization")
    _attributes = ("description",)

    name: str
    description: Optional[str]
    organization: Optional[str]

    local_id: Optional[str]
    local_data: Optional[Any]


class InfraVLAN(InfrahubModel):
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


class InfraVRF(InfrahubModel):
    _modelname = "InfraVRF"
    _identifiers = ("name", "namespace")
    _attributes = ("organization", "import_rt", "export_rt", "description", "vrf_rd")

    name: str
    description: Optional[str]
    vrf_rd: Optional[str]
    organization: Optional[str]
    namespace: Optional[str]
    import_rt: List[str] = []
    export_rt: List[str] = []

    local_id: Optional[str]
    local_data: Optional[Any]
