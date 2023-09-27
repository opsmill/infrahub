from infrahub_sync.adapters.nautobot import NautobotAdapter

from .models import BuiltinLocation, BuiltinRole, BuiltinTag, InfraRack


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class NautobotSync(NautobotAdapter):
    BuiltinTag = BuiltinTag
    BuiltinRole = BuiltinRole
    BuiltinLocation = BuiltinLocation
    InfraRack = InfraRack
