from infrahub_sync.adapters.netbox import NetboxAdapter

from .models import (
    BuiltinLocation,
    BuiltinRole,
    BuiltinTag,
    InfraRack,
    OrgaManufacturer,
    OrgaProvider,
    TemplateDeviceType,
)


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class NetboxSync(NetboxAdapter):
    BuiltinTag = BuiltinTag
    BuiltinRole = BuiltinRole
    BuiltinLocation = BuiltinLocation
    TemplateDeviceType = TemplateDeviceType
    OrgaManufacturer = OrgaManufacturer
    InfraRack = InfraRack
    OrgaProvider = OrgaProvider
