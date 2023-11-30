from infrahub_sync.adapters.infrahub import InfrahubAdapter

from .models import (
    BuiltinLocation,
    BuiltinRole,
    BuiltinTag,
    CoreOrganization,
    CoreStandardGroup,
    InfraCircuit,
    InfraDevice,
    InfraIPAddress,
    InfraPrefix,
    InfraProviderNetwork,
    InfraRack,
    InfraRouteTarget,
    InfraVLAN,
    InfraVRF,
    TemplateCircuitType,
    TemplateDeviceType,
)


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class InfrahubSync(InfrahubAdapter):
    CoreStandardGroup = CoreStandardGroup
    BuiltinTag = BuiltinTag
    CoreOrganization = CoreOrganization
    BuiltinRole = BuiltinRole
    BuiltinLocation = BuiltinLocation
    InfraDevice = InfraDevice
    InfraIPAddress = InfraIPAddress
    InfraVLAN = InfraVLAN
    InfraCircuit = InfraCircuit
    TemplateCircuitType = TemplateCircuitType
    TemplateDeviceType = TemplateDeviceType
    InfraProviderNetwork = InfraProviderNetwork
    InfraPrefix = InfraPrefix
    InfraRack = InfraRack
    InfraRouteTarget = InfraRouteTarget
    InfraVRF = InfraVRF
