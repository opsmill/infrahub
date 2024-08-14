from typing import Any, Optional

from infrahub_sync.adapters.observium import ObserviumModel


# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class CoreStandardGroup(ObserviumModel):
    _modelname = "CoreStandardGroup"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None


class InfraDevice(ObserviumModel):
    _modelname = "InfraDevice"
    _identifiers = ("name",)
    _attributes = ("primary_address", "platform", "description", "type")
    name: str
    description: Optional[str] = None
    type: str
    primary_address: Optional[str] = None
    platform: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None


class IpamIPAddress(ObserviumModel):
    _modelname = "IpamIPAddress"
    _identifiers = ("address",)
    _attributes = ("description",)
    address: str
    description: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None
