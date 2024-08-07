from typing import Any, Optional

from infrahub_sync.adapters.librenms import LibrenmsModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------


class CoreStandardGroup(LibrenmsModel):
    _modelname = "CoreStandardGroup"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None


class InfraDevice(LibrenmsModel):
    _modelname = "InfraDevice"
    _identifiers = ("name",)
    _attributes = ("site", "type")
    name: str
    type: str
    site: str
    local_id: Optional[str] = None
    local_data: Optional[Any] = None


class IpamIPAddress(LibrenmsModel):
    _modelname = "IpamIPAddress"
    _identifiers = ("address",)
    _attributes = ("description",)
    address: str
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None


class LocationSite(LibrenmsModel):
    _modelname = "LocationSite"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None
