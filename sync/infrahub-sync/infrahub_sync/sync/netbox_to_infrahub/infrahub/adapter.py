from infrahub_sync.adapters.infrahub import InfrahubAdapter

from .models import (
   BuiltinTag,
   BuiltinRole,
   BuiltinLocation,
   InfraCircuit,
   TemplateCircuitType,
   TemplateDeviceType,
   InfraProviderNetwork,
   InfraRack,
   OrgaProvider,
)

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class InfrahubSync(InfrahubAdapter):
    BuiltinTag = BuiltinTag
    BuiltinRole = BuiltinRole
    BuiltinLocation = BuiltinLocation
    InfraCircuit = InfraCircuit
    TemplateCircuitType = TemplateCircuitType
    TemplateDeviceType = TemplateDeviceType
    InfraProviderNetwork = InfraProviderNetwork
    InfraRack = InfraRack
    OrgaProvider = OrgaProvider
