from typing import Any, List, Optional

from infrahub_sync.adapters.infrahub import InfrahubModel


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class InfraAutonomousSystem(InfrahubModel):
    _modelname = "InfraAutonomousSystem"
    _identifiers = ("asn",)
    _attributes = ("name", "description", "irr_as_set", "ipv4_max_prefixes", "ipv6_max_prefixes", "affiliated")
    name: str
    asn: int
    description: Optional[str] = None
    irr_as_set: Optional[str] = None
    ipv4_max_prefixes: Optional[int] = None
    ipv6_max_prefixes: Optional[int] = None
    affiliated: Optional[bool] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None


class InfraBGPPeerGroup(InfrahubModel):
    _modelname = "InfraBGPPeerGroup"
    _identifiers = ("name",)
    _attributes = ("import_policies", "export_policies", "bgp_communities", "description", "status")
    name: str
    description: Optional[str] = None
    status: Optional[str] = None
    import_policies: Optional[List[str]] = []
    export_policies: Optional[List[str]] = []
    bgp_communities: Optional[List[str]] = []

    local_id: Optional[str] = None
    local_data: Optional[Any] = None


class InfraBGPRoutingPolicy(InfrahubModel):
    _modelname = "InfraBGPRoutingPolicy"
    _identifiers = ("name",)
    _attributes = ("bgp_communities", "address_family", "label", "description", "policy_type", "weight")
    address_family: int
    label: Optional[str] = None
    description: Optional[str] = None
    name: str
    policy_type: str
    weight: Optional[int] = 1000
    bgp_communities: Optional[List[str]] = []

    local_id: Optional[str] = None
    local_data: Optional[Any] = None


class InfraBGPCommunity(InfrahubModel):
    _modelname = "InfraBGPCommunity"
    _identifiers = ("name",)
    _attributes = ("description", "value", "label", "community_type")
    description: Optional[str] = None
    name: str
    value: str
    label: Optional[str] = None
    community_type: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None


class InfraIXP(InfrahubModel):
    _modelname = "InfraIXP"
    _identifiers = ("name",)
    _attributes = ("export_policies", "bgp_communities", "import_policies", "description", "status")
    description: Optional[str] = None
    name: str
    status: Optional[str] = "enabled"
    export_policies: Optional[List[str]] = []
    bgp_communities: Optional[List[str]] = []
    import_policies: Optional[List[str]] = []

    local_id: Optional[str] = None
    local_data: Optional[Any] = None


class InfraIXPConnection(InfrahubModel):
    _modelname = "InfraIXPConnection"
    _identifiers = ("name",)
    _attributes = ("internet_exchange_point", "status", "vlan", "description", "peeringdb_netixlan")
    status: Optional[str] = "enabled"
    vlan: Optional[int] = None
    name: str
    description: Optional[str] = None
    peeringdb_netixlan: Optional[int] = None
    internet_exchange_point: str

    local_id: Optional[str] = None
    local_data: Optional[Any] = None
