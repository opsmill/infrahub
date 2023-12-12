from typing import Any, List, Optional

from infrahub_sync.adapters.nautobot import NautobotModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------


class InfraVLAN(NautobotModel):
    _modelname = "InfraVLAN"
    _identifiers = ("name", "vlan_id")
    _attributes = ("description",)

    name: str
    description: Optional[str]
    vlan_id: int

    local_id: Optional[str]
    local_data: Optional[Any]
