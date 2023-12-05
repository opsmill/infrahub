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
    InfraIPAddress,
    InfraInterface,
    InfraPlatform,
    InfraPrefix,
    InfraProviderNetwork,
    InfraRack,
    InfraRearPort,
    InfraRouteTarget,
    InfraVLAN,
    InfraVRF,
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
    CoreOrganization = CoreOrganization
    BuiltinRole = BuiltinRole
    BuiltinLocation = BuiltinLocation
    InfraAutonomousSystem = InfraAutonomousSystem
    InfraCircuit = InfraCircuit
    TemplateCircuitType = TemplateCircuitType
    InfraDevice = InfraDevice
    TemplateDeviceType = TemplateDeviceType
    InfraFrontPort = InfraFrontPort
    InfraRearPort = InfraRearPort
    InfraIPAddress = InfraIPAddress
    TemplateLocationType = TemplateLocationType
    InfraPlatform = InfraPlatform
    InfraProviderNetwork = InfraProviderNetwork
    InfraPrefix = InfraPrefix
    InfraRack = InfraRack
    InfraRouteTarget = InfraRouteTarget
    InfraVLAN = InfraVLAN
    InfraVRF = InfraVRF
    InfraInterface = InfraInterface
