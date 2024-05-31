from infrahub_sync.adapters.infrahub import InfrahubAdapter

from .sync_models import (
    BuiltinLocation,
    CoreOrganization,
    InfraDevice,
    InfraIPAddress,
    InfraInterfaceL3,
    InfraNOSVersion,
    InfraPartNumber,
    InfraPlatform,
    InfraPrefix,
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
    InfraPartNumber = InfraPartNumber
    InfraPlatform = InfraPlatform
    InfraVLAN = InfraVLAN
    InfraVRF = InfraVRF
    TemplateDeviceType = TemplateDeviceType
    InfraInterfaceL3 = InfraInterfaceL3
    InfraIPAddress = InfraIPAddress
    InfraPrefix = InfraPrefix
