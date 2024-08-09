from typing import Any, List, Optional

from infrahub_sync.adapters.peeringmanager import PeeringmanagerModel


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class InfraAutonomousSystem(PeeringmanagerModel):
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


class InfraBGPCommunity(PeeringmanagerModel):
    _modelname = "InfraBGPCommunity"
    _identifiers = ("name",)
    _attributes = ("label", "description", "value", "community_type")
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    value: str
    community_type: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None


class InfraBGPRoutingPolicy(PeeringmanagerModel):
    _modelname = "InfraBGPRoutingPolicy"
    _identifiers = ("name",)
    _attributes = ("bgp_communities", "label", "description", "policy_type", "weight", "address_family")
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    policy_type: str
    weight: Optional[int] = 1000
    address_family: int
    bgp_communities: Optional[List[str]] = []

    local_id: Optional[str] = None
    local_data: Optional[Any] = None
