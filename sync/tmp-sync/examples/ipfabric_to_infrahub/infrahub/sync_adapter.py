from infrahub_sync.adapters.infrahub import InfrahubAdapter

from .sync_models import (
    InfraDevice,
    InfraInterfaceL3,
    InfraNOSVersion,
    InfraPartNumber,
    InfraPlatform,
    InfraVLAN,
    InfraVRF,
    LocationGeneric,
    OrganizationGeneric,
    TemplateDeviceType,
)


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class InfrahubSync(InfrahubAdapter):
    InfraDevice = InfraDevice
    InfraInterfaceL3 = InfraInterfaceL3
    InfraNOSVersion = InfraNOSVersion
    InfraPartNumber = InfraPartNumber
    InfraPlatform = InfraPlatform
    InfraVLAN = InfraVLAN
    InfraVRF = InfraVRF
    LocationGeneric = LocationGeneric
    OrganizationGeneric = OrganizationGeneric
    TemplateDeviceType = TemplateDeviceType
