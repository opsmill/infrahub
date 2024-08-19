from infrahub_sync.adapters.peeringmanager import PeeringmanagerAdapter

from .sync_models import (
    InfraAutonomousSystem,
    InfraBGPCommunity,
    InfraBGPPeerGroup,
    InfraBGPRoutingPolicy,
    InfraIXP,
    InfraIXPConnection,
    IpamIPAddress,
)


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class PeeringmanagerSync(PeeringmanagerAdapter):
    InfraAutonomousSystem = InfraAutonomousSystem
    InfraBGPPeerGroup = InfraBGPPeerGroup
    IpamIPAddress = IpamIPAddress
    InfraBGPRoutingPolicy = InfraBGPRoutingPolicy
    InfraBGPCommunity = InfraBGPCommunity
    InfraIXP = InfraIXP
    InfraIXPConnection = InfraIXPConnection
