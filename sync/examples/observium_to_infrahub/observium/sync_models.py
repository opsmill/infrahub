from typing import Any, List, Optional

from infrahub_sync.adapters.observium import ObserviumModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------

class InfraDevice(ObserviumModel):
    _modelname = "InfraDevice"
    _identifiers = ("name",)
    _attributes = ("description", "serial_number", "type")
    name: str
    hostname: str
    description: Optional[str] = None
    serial_number: Optional[str] = None
    type: Optional[str] = None
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