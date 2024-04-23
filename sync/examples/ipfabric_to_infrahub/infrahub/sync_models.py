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

class InfraPlatform(InfrahubModel):
    _modelname = "InfraPlatform"
    _identifiers = ("name",)
    _attributes = ("description",)
    description: Optional[str] = None
    name: str
    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class TemplateDeviceType(InfrahubModel):
    _modelname = "TemplateDeviceType"
    _identifiers = ("name", "manufacturer")
    _attributes = ("description",)
    description: Optional[str] = None
    name: str
    manufacturer: str
    local_id: Optional[str] = None
    local_data: Optional[Any] = None