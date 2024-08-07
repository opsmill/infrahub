from infrahub_sync.adapters.infrahub import InfrahubAdapter

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
    NautobotNamespace,
    OrganizationGeneric,
    RoleGeneric,
    TemplateCircuitType,
    TemplateDeviceType,
    TemplateLocationType,
)


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class InfrahubSync(InfrahubAdapter):
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
    NautobotNamespace = NautobotNamespace
    OrganizationGeneric = OrganizationGeneric
    RoleGeneric = RoleGeneric
    TemplateCircuitType = TemplateCircuitType
    TemplateDeviceType = TemplateDeviceType
    TemplateLocationType = TemplateLocationType
