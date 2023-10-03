from infrahub_sync.adapters.netbox import NetboxAdapter

from .models import (
   CoreStandardGroup,
   BuiltinTag,
   CoreOrganization,
   BuiltinRole,
   BuiltinLocation,
   InfraCircuit,
   TemplateCircuitType,
   InfraDevice,
   TemplateDeviceType,
   InfraIPAddress,
   InfraProviderNetwork,
   InfraPrefix,
   InfraRack,
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
    CoreOrganization = CoreOrganization
    BuiltinRole = BuiltinRole
    BuiltinLocation = BuiltinLocation
    InfraCircuit = InfraCircuit
    TemplateCircuitType = TemplateCircuitType
    InfraDevice = InfraDevice
    TemplateDeviceType = TemplateDeviceType
    InfraIPAddress = InfraIPAddress
    InfraProviderNetwork = InfraProviderNetwork
    InfraPrefix = InfraPrefix
    InfraRack = InfraRack
    InfraRouteTarget = InfraRouteTarget
    InfraVLAN = InfraVLAN
    InfraVRF = InfraVRF
