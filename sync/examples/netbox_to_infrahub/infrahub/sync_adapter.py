from infrahub_sync.adapters.infrahub import InfrahubAdapter

from .sync_models import (
    BuiltinLocation,
    BuiltinRole,
    BuiltinTag,
    CoreStandardGroup,
    InfraRack,
    OrganizationGeneric,
)


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class InfrahubSync(InfrahubAdapter):
    CoreStandardGroup = CoreStandardGroup
    BuiltinTag = BuiltinTag
    BuiltinLocation = BuiltinLocation
    BuiltinRole = BuiltinRole
    InfraRack = InfraRack
    OrganizationGeneric = OrganizationGeneric
