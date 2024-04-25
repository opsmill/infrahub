from typing import Any, List, Optional

from infrahub_sync.adapters.infrahub import InfrahubModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------

class BuiltinLocation(InfrahubModel):
    _modelname = "BuiltinLocation"
    _identifiers = ("name",)
    _attributes = ("description", "type")
    name: str
    description: Optional[str] = None
    type: str
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class CoreOrganization(InfrahubModel):
    _modelname = "CoreOrganization"
    _identifiers = ("name",)
    _attributes = ("type",)
    name: str
    type: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraDevice(InfrahubModel):
    _modelname = "InfraDevice"
    _identifiers = ("hostname", "location")
    _attributes = ("platform", "version", "model", "serial_number", "fqdn", "hardware_serial_number")
    serial_number: str
    fqdn: Optional[str] = None
    hostname: str
    hardware_serial_number: str
    platform: Optional[str] = None
    location: str
    version: Optional[str] = None
    model: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraNOSVersion(InfrahubModel):
    _modelname = "InfraNOSVersion"
    _identifiers = ("manufacturer", "version")
    _attributes = ("platform", "model")
    version: str
    platform: Optional[str] = None
    manufacturer: str
    model: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraPlatform(InfrahubModel):
    _modelname = "InfraPlatform"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class TemplateDeviceType(InfrahubModel):
    _modelname = "TemplateDeviceType"
    _identifiers = ("name", "manufacturer")
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    manufacturer: str
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraVLAN(InfrahubModel):
    _modelname = "InfraVLAN"
    _identifiers = ("location", "vlan_id")
    _attributes = ("name", "description")
    name: Optional[str] = None
    description: Optional[str] = None
    vlan_id: int
    location: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraVRF(InfrahubModel):
    _modelname = "InfraVRF"
    _identifiers = ("name",)
    _attributes = ("vrf_rd",)
    name: str
    vrf_rd: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraPartNumber(InfrahubModel):
    _modelname = "InfraPartNumber"
    _identifiers = ("device", "name")
    _attributes = ("manufacturer", "model", "part_sn", "part_vid", "description", "part_id")
    part_sn: Optional[str] = None
    name: Optional[str] = None
    part_vid: Optional[str] = None
    description: Optional[str] = None
    part_id: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    device: Optional[str] = None
    local_id: Optional[str] = None
    local_data: Optional[Any] = None