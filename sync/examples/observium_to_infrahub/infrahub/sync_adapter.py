from infrahub_sync.adapters.infrahub import InfrahubAdapter

from .sync_models import (
    InfraDevice,
    IpamIPAddress,
)


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class InfrahubSync(InfrahubAdapter):
    InfraDevice = InfraDevice
    IpamIPAddress = IpamIPAddress
