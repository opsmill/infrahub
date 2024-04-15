from infrahub_sync.adapters.nautobot import NautobotAdapter

from .sync_models import (
    BuiltinTag,
    CoreStandardGroup,
    InfraAutonomousSystem,
    InfraCircuit,
    InfraDevice,
    InfraFrontPort,
    InfraIPAddress,
    InfraInterfaceL2L3,
    InfraPlatform,
    InfraPrefix,
    InfraProviderNetwork,
    InfraRack,
    InfraRearPort,
    InfraRouteTarget,
    InfraVLAN,
    InfraVRF,
    LocationGeneric,
    RoleGeneric,
    StatusGeneric,
    TemplateCircuitType,
    TemplateDeviceType,
    TemplateLocationType,
)


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class NautobotSync(NautobotAdapter):
    CoreStandardGroup = CoreStandardGroup
    BuiltinTag = BuiltinTag
    InfraAutonomousSystem = InfraAutonomousSystem
    InfraCircuit = InfraCircuit
    InfraDevice = InfraDevice
    InfraFrontPort = InfraFrontPort
    InfraIPAddress = InfraIPAddress
    InfraInterfaceL2L3 = InfraInterfaceL2L3
    InfraPlatform = InfraPlatform
    InfraPrefix = InfraPrefix
    InfraProviderNetwork = InfraProviderNetwork
    InfraRack = InfraRack
    InfraRearPort = InfraRearPort
    InfraRouteTarget = InfraRouteTarget
    InfraVLAN = InfraVLAN
    InfraVRF = InfraVRF
    LocationGeneric = LocationGeneric
    RoleGeneric = RoleGeneric
    StatusGeneric = StatusGeneric
    TemplateCircuitType = TemplateCircuitType
    TemplateDeviceType = TemplateDeviceType
    TemplateLocationType = TemplateLocationType
