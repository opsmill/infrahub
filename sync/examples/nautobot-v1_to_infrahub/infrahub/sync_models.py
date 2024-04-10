from typing import Any, List, Optional

from infrahub_sync.adapters.infrahub import InfrahubModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------

class CoreStandardGroup(InfrahubModel):
    _modelname: str = "CoreStandardGroup"
    _identifiers: List[str] = ("name",)
    _attributes: List[str] = ("description",)
    name: str
    description: Optional[str]
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class BuiltinTag(InfrahubModel):
    _modelname: str = "BuiltinTag"
    _identifiers: List[str] = ("name",)
    _attributes: List[str] = ("description",)
    name: str
    description: Optional[str]
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraAutonomousSystem(InfrahubModel):
    _modelname: str = "InfraAutonomousSystem"
    _identifiers: List[str] = ("name",)
    _attributes: List[str] = ("organization", "description")
    name: str
    asn: int
    description: Optional[str]
    organization: str
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraCircuit(InfrahubModel):
    _modelname: str = "InfraCircuit"
    _identifiers: List[str] = ("circuit_id",)
    _attributes: List[str] = ("provider", "description", "vendor_id")
    circuit_id: str
    description: Optional[str]
    vendor_id: Optional[str]
    provider: str
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraDevice(InfrahubModel):
    _modelname: str = "InfraDevice"
    _identifiers: List[str] = ("location", "organization", "name")
    _attributes: List[str] = ("tags", "platform", "role")
    name: str
    role: Optional[str]
    location: str
    tags: List[str] = []
    platform: Optional[str]
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraIPAddress(InfrahubModel):
    _modelname: str = "InfraIPAddress"
    _identifiers: List[str] = ("address", "vrf")
    _attributes: List[str] = ("description",)
    address: str
    description: Optional[str]
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraPlatform(InfrahubModel):
    _modelname: str = "InfraPlatform"
    _identifiers: List[str] = ("name", "manufacturer")
    _attributes: List[str] = ("description", "napalm_driver")
    name: str
    description: Optional[str]
    napalm_driver: Optional[str]
    manufacturer: Optional[str]
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraPrefix(InfrahubModel):
    _modelname: str = "InfraPrefix"
    _identifiers: List[str] = ("prefix", "vrf", "organization")
    _attributes: List[str] = ("location", "role", "description")
    role: Optional[str]
    prefix: str
    description: Optional[str]
    organization: Optional[str]
    location: Optional[str]
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraRouteTarget(InfrahubModel):
    _modelname: str = "InfraRouteTarget"
    _identifiers: List[str] = ("name", "organization")
    _attributes: List[str] = ("description",)
    name: str
    description: Optional[str]
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraVLAN(InfrahubModel):
    _modelname: str = "InfraVLAN"
    _identifiers: List[str] = ("name", "vlan_id", "location", "organization")
    _attributes: List[str] = ("description", "role")
    name: str
    description: Optional[str]
    vlan_id: int
    role: str
    location: Optional[str]
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraVRF(InfrahubModel):
    _modelname: str = "InfraVRF"
    _identifiers: List[str] = ("name",)
    _attributes: List[str] = ("import_rt", "export_rt", "vrf_rd", "description")
    vrf_rd: Optional[str]
    name: str
    description: Optional[str]
    import_rt: Optional[str]
    export_rt: Optional[str]
    local_id: Optional[str] = None
    local_data: Optional[Any] = None