from infrahub_sync.adapters.nautobot import NautobotAdapter

from .models import (
    BuiltinLocation,
    BuiltinRole,
    BuiltinTag,
    CoreOrganization,
    CoreStandardGroup,
    InfraAutonomousSystem,
    InfraCircuit,
    InfraDevice,
    InfraFrontPort,
    InfraInterfaceL2L3,
    InfraIPAddress,
    InfraPlatform,
    InfraPrefix,
    InfraProviderNetwork,
    InfraRack,
    InfraRearPort,
    InfraRouteTarget,
    InfraVLAN,
    InfraVRF,
    NautobotNamespace,
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
    TemplateCircuitType = TemplateCircuitType
    InfraDevice = InfraDevice
    TemplateDeviceType = TemplateDeviceType
    InfraFrontPort = InfraFrontPort
    InfraInterfaceL2L3 = InfraInterfaceL2L3
    InfraIPAddress = InfraIPAddress
    TemplateLocationType = TemplateLocationType
    NautobotNamespace = NautobotNamespace
    InfraPlatform = InfraPlatform
    InfraProviderNetwork = InfraProviderNetwork
    InfraPrefix = InfraPrefix
    InfraRack = InfraRack
    InfraRearPort = InfraRearPort
    InfraRouteTarget = InfraRouteTarget
    InfraVLAN = InfraVLAN
    InfraVRF = InfraVRF
    CoreOrganization = CoreOrganization
    BuiltinRole = BuiltinRole
    BuiltinLocation = BuiltinLocation
