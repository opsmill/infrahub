from infrahub_sync.adapters.infrahub import InfrahubAdapter

from .sync_models import (
    BuiltinTag,
    CoreStandardGroup,
    InfraAutonomousSystem,
    InfraCircuit,
    InfraDevice,
    InfraIPAddress,
    InfraPlatform,
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
class InfrahubSync(InfrahubAdapter):
    CoreStandardGroup = CoreStandardGroup
    BuiltinTag = BuiltinTag
    InfraPlatform = InfraPlatform
    InfraDevice = InfraDevice
    InfraCircuit = InfraCircuit
    InfraAutonomousSystem = InfraAutonomousSystem
    InfraIPAddress = InfraIPAddress
    InfraVLAN = InfraVLAN
    InfraPrefix = InfraPrefix
    InfraVRF = InfraVRF
    InfraRouteTarget = InfraRouteTarget
