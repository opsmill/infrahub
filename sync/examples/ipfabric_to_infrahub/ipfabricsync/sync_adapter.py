from infrahub_sync.adapters.ipfabricsync import IpfabricsyncAdapter

from .sync_models import (
    BuiltinLocation,
    CoreOrganization,
    InfraPlatform,
    TemplateDeviceType,
)


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class IpfabricsyncSync(IpfabricsyncAdapter):
    BuiltinLocation = BuiltinLocation
    CoreOrganization = CoreOrganization
    InfraPlatform = InfraPlatform
    TemplateDeviceType = TemplateDeviceType
