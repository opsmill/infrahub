from typing import Any, List, Optional
import netutils.regex
import netutils.ip

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

    @classmethod
    def filter_records(cls, records: List[dict]) -> List[dict]:
        filtered_records = []
        for record in records:
            include = True
            if include:
                filtered_records.append(record)
        return filtered_records

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

    @classmethod
    def filter_records(cls, records: List[dict]) -> List[dict]:
        filtered_records = []
        for record in records:
            include = True
            try:
                record_value = int(record.get('device_id', 0))
                if not (record_value > 100):
                    include = False
            except Exception as e:
                print(f"Error evaluating filter: 'device_id > 100' with record {record}: {e}")
                include = False
            try:
                record_value = int(record.get('device_id', 0))
                if not (record_value <= 200):
                    include = False
            except Exception as e:
                print(f"Error evaluating filter: 'device_id <= 200' with record {record}: {e}")
                include = False
            try:
                if not netutils.regex.regex_search('xxx', record.get('hostname', '')):
                    include = False
            except Exception as e:
                print(f"Error evaluating filter: 'hostname | netutils.regex.regex_search('xxx')' with record {record}: {e}")
                include = False
            try:
                if not netutils.regex.regex_match('^pe-[0-9]{3}$', record.get('name', '')):
                    include = False
            except Exception as e:
                print(f"Error evaluating filter: 'name | netutils.regex.regex_match('^pe-[0-9]{3}$')' with record {record}: {e}")
                include = False
            if include:
                filtered_records.append(record)
        return filtered_records

class IpamIPAddress(ObserviumModel):
    _modelname = "IpamIPAddress"
    _identifiers = ("address",)
    _attributes = ("description",)
    address: str
    description: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

    @classmethod
    def filter_records(cls, records: List[dict]) -> List[dict]:
        filtered_records = []
        for record in records:
            include = True
            try:
                if not (netutils.ip.is_ip_within(record.get('ip'), '100.125.0.0/16')):
                    include = False
            except Exception as e:
                print(f"Error evaluating filter: 'netutils.ip.is_ip_within(record.get('ip'), '100.125.0.0/16')' with record {record}: {e}")
                include = False
            try:
                if not netutils.regex.regex_search('xxx', record.get('hostname', '')):
                    include = False
            except Exception as e:
                print(f"Error evaluating filter: 'hostname | netutils.regex.regex_search('xxx')' with record {record}: {e}")
                include = False
            try:
                if not netutils.regex.regex_match('^pe-[0-9]{3}$', record.get('name', '')):
                    include = False
            except Exception as e:
                print(f"Error evaluating filter: 'name | netutils.regex.regex_match('^pe-[0-9]{3}$')' with record {record}: {e}")
                include = False
            if include:
                filtered_records.append(record)
        return filtered_records
