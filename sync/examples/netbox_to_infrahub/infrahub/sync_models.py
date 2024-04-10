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

class InfraCircuit(InfrahubModel):
    _modelname: str = "InfraCircuit"
    _identifiers: List[str] = ("name",)
    _attributes: List[str] = ("provider", "description", "vendor_id")
    circuit_id: str
    description: Optional[str]
    vendor_id: Optional[str]
    provider: str
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraDevice(InfrahubModel):
    _modelname: str = "InfraDevice"
    _identifiers: List[str] = ("name", "location", "rack", "organization")
    _attributes: List[str] = ("tags", "description", "role")
    name: str
    description: Optional[str]
    role: Optional[str]
    location: str
    tags: List[str] = []
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

class InfraPrefix(InfrahubModel):
    _modelname: str = "InfraPrefix"
    _identifiers: List[str] = ("prefix", "vrf")
    _attributes: List[str] = ("organization", "location", "role", "description")
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
    _identifiers: List[str] = ("name", "vlan_id", "location", "vlan_group")
    _attributes: List[str] = ("description",)
    name: str
    description: Optional[str]
    vlan_id: int
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