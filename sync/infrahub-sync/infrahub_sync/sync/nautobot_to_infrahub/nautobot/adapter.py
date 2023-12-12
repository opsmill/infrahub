from infrahub_sync.adapters.nautobot import NautobotAdapter

from .models import (
    InfraVLAN,
)


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class NautobotSync(NautobotAdapter):
    InfraVLAN = InfraVLAN
