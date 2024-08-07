from infrahub_sync.adapters.librenms import LibrenmsAdapter

from .sync_models import (
    CoreStandardGroup,
    InfraDevice,
    IpamIPAddress,
    LocationSite,
)


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class LibrenmsSync(LibrenmsAdapter):
    CoreStandardGroup = CoreStandardGroup
    InfraDevice = InfraDevice
    IpamIPAddress = IpamIPAddress
    LocationSite = LocationSite
