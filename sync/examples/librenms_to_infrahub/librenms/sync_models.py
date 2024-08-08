from typing import Any, List, Optional

import netutils.ip
import netutils.regex

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
    _attributes = ("site", "description", "serial_number", "type")
    name: str
    description: Optional[str] = None
    serial_number: Optional[str] = None
    type: str
    site: str

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

    @classmethod
    def filter_records(cls, records: List[Any]) -> List[Any]:
        filtered_records = []
        for record in records:
            include = True
            try:
                if netutils.regex.regex_search("xxx", "hostname"):
                    include = False
            except Exception as e:
                print(
                    f"Error evaluating filter: 'netutils.regex.regex_search('xxx', 'hostname')' with record {record}: {e}"
                )
                include = False
            if include:
                filtered_records.append(record)
        return filtered_records


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
