from typing import Any, List, Optional

import netutils.ip
import netutils.regex

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
    _attributes = ("primary_address", "platform", "description", "serial_number", "type")
    name: str
    description: Optional[str] = None
    type: str
    serial_number: Optional[str] = None
    primary_address: Optional[str] = None
    platform: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

    @classmethod
    def filter_records(cls, records: List[Any]) -> List[Any]:
        filtered_records = []
        for record in records:
            include = True
            try:
                field_value = (
                    getattr(record, "device_id", 0) if not isinstance(record, dict) else record.get("device_id", 0)
                )
                record_value = int(field_value)
                if not (record_value > 100):
                    include = False
            except Exception as e:
                print(f"Error evaluating filter: 'device_id > 100' with record {record}: {e}")
                include = False
            try:
                field_value = (
                    getattr(record, "device_id", 0) if not isinstance(record, dict) else record.get("device_id", 0)
                )
                record_value = int(field_value)
                if not (record_value <= 200):
                    include = False
            except Exception as e:
                print(f"Error evaluating filter: 'device_id <= 200' with record {record}: {e}")
                include = False
            try:
                if netutils.regex.regex_search("xxx", "hostname"):
                    include = False
            except Exception as e:
                print(
                    f"Error evaluating filter: 'netutils.regex.regex_search('xxx', 'hostname')' with record {record}: {e}"
                )
                include = False
            try:
                if netutils.regex.regex_match("^pe-[0-9]{3}$", "hostname"):
                    include = False
            except Exception as e:
                print(
                    f"Error evaluating filter: 'netutils.regex.regex_match('^pe-[0-9]{3}$', 'hostname')' with record {record}: {e}"
                )
                include = False
            if include:
                filtered_records.append(record)
        return filtered_records


class IpamIPAddress(InfrahubModel):
    _modelname = "IpamIPAddress"
    _identifiers = ("address",)
    _attributes = ("description",)
    address: str
    description: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

    @classmethod
    def filter_records(cls, records: List[Any]) -> List[Any]:
        filtered_records = []
        for record in records:
            include = True
            try:
                if netutils.ip.is_ip_within(record.get("ip"), "10.0.0.0/8"):
                    include = False
            except Exception as e:
                print(
                    f"Error evaluating filter: 'netutils.ip.is_ip_within(record.get('ip'), '10.0.0.0/8')' with record {record}: {e}"
                )
                include = False
            try:
                if netutils.regex.regex_search("xxx", "hostname"):
                    include = False
            except Exception as e:
                print(
                    f"Error evaluating filter: 'netutils.regex.regex_search('xxx', 'hostname')' with record {record}: {e}"
                )
                include = False
            try:
                if netutils.regex.regex_match("^pe-[0-9]{3}$", "hostname"):
                    include = False
            except Exception as e:
                print(
                    f"Error evaluating filter: 'netutils.regex.regex_match('^pe-[0-9]{3}$', 'hostname')' with record {record}: {e}"
                )
                include = False
            if include:
                filtered_records.append(record)
        return filtered_records
