from infrahub_sync.adapters.infrahub import InfrahubAdapter

from .sync_models import (
    BuiltinLocation,
    CoreOrganization,
    InfraDevice,
    InfraNOSVersion,
    InfraPartNumber,
    InfraPlatform,
    InfraVLAN,
    InfraVRF,
    TemplateDeviceType,
)


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class InfrahubSync(InfrahubAdapter):
    BuiltinLocation = BuiltinLocation
    CoreOrganization = CoreOrganization
    InfraDevice = InfraDevice
    InfraNOSVersion = InfraNOSVersion
    InfraPlatform = InfraPlatform
    TemplateDeviceType = TemplateDeviceType
    InfraVLAN = InfraVLAN
    InfraVRF = InfraVRF
    InfraPartNumber = InfraPartNumber
