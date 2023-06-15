from infrahub_sync.adapters.netbox import NetboxAdapter

from .models import Location, Rack, Role, Tag


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class NetboxSync(NetboxAdapter):
    tag = Tag
    role = Role
    rack = Rack
    location = Location
