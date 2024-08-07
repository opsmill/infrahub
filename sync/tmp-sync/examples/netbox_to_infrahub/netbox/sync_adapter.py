from infrahub_sync.adapters.netbox import NetboxAdapter

from .sync_models import (
    BuiltinTag,
    CoreStandardGroup,
    InfraCircuit,
    InfraDevice,
    InfraIPAddress,
    InfraInterfaceL2L3,
    InfraPrefix,
    InfraProviderNetwork,
    InfraRack,
    InfraRouteTarget,
    InfraVLAN,
    InfraVRF,
    LocationGeneric,
    OrganizationGeneric,
    RoleGeneric,
    TemplateCircuitType,
    TemplateDeviceType,
)


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class NetboxSync(NetboxAdapter):
    CoreStandardGroup = CoreStandardGroup
    BuiltinTag = BuiltinTag
    InfraCircuit = InfraCircuit
    TemplateCircuitType = TemplateCircuitType
    InfraDevice = InfraDevice
    TemplateDeviceType = TemplateDeviceType
    InfraInterfaceL2L3 = InfraInterfaceL2L3
    InfraIPAddress = InfraIPAddress
    InfraProviderNetwork = InfraProviderNetwork
    InfraPrefix = InfraPrefix
    InfraRack = InfraRack
    InfraRouteTarget = InfraRouteTarget
    InfraVLAN = InfraVLAN
    InfraVRF = InfraVRF
    OrganizationGeneric = OrganizationGeneric
    RoleGeneric = RoleGeneric
    LocationGeneric = LocationGeneric
