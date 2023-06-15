from infrahub_sync.adapters.infrahub import InfrahubAdapter

from .models import (
   Tag,
   Role,
   Rack,
   Location,
)

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class InfrahubSync(InfrahubAdapter):
    tag = Tag
    role = Role
    rack = Rack
    location = Location
