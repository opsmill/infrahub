from typing import Any, List, Optional

from infrahub_sync.adapters.infrahub import InfrahubModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------

class CoreStandardGroup(InfrahubModel):
    _modelname = "CoreStandardGroup"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraDevice(InfrahubModel):
    _modelname = "InfraDevice"
    _identifiers = ("name",)
    _attributes = ("site", "type")
    name: str
    type: str
    site: str
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class IpamIPAddress(InfrahubModel):
    _modelname = "IpamIPAddress"
    _identifiers = ("address",)
    _attributes = ("description",)
    address: str
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class LocationSite(InfrahubModel):
    _modelname = "LocationSite"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None