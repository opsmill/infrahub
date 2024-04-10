from infrahub_sync.adapters.netbox import NetboxAdapter

from .sync_models import (
    BuiltinTag,
    CoreStandardGroup,
    InfraCircuit,
    InfraDevice,
    InfraIPAddress,
    InfraPrefix,
    InfraRouteTarget,
    InfraVLAN,
    InfraVRF,
)


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class NetboxSync(NetboxAdapter):
    CoreStandardGroup = CoreStandardGroup
    BuiltinTag = BuiltinTag
    InfraDevice = InfraDevice
    InfraCircuit = InfraCircuit
    InfraIPAddress = InfraIPAddress
    InfraVLAN = InfraVLAN
    InfraPrefix = InfraPrefix
    InfraVRF = InfraVRF
    InfraRouteTarget = InfraRouteTarget
