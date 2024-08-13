from typing import Any, List, Optional

from infrahub_sync.adapters.observium import ObserviumModel
from infrahub_sync.adapters.utils import apply_filters, apply_transforms


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

    @classmethod
    def filter_records(cls, records: List[Any]) -> List[Any]:
        """Filter records based on the defined filters."""
        filters = [
            {"field": "device_id", "operation": ">", "value": 100},
            {"field": "device_id", "operation": "<=", "value": 200},
            {"field": "hostname", "operation": "regex", "value": "^pe-[0-9]{3}$"},
        ]
        return [record for record in records if apply_filters(record, filters)]


class IpamIPAddress(ObserviumModel):
    _modelname = "IpamIPAddress"
    _identifiers = ("address",)
    _attributes = ("description",)
    address: str
    description: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

    @classmethod
    def filter_records(cls, records: List[Any]) -> List[Any]:
        """Filter records based on the defined filters."""
        filters = [
            {"field": "hostname", "operation": "regex", "value": "^pe-[0-9]{3}$"},
            {"field": "ip", "operation": "is_ip_within", "value": "10.0.0.0/8"},
        ]
        return [record for record in records if apply_filters(record, filters)]

    @classmethod
    def transform_records(cls, records: List[Any]) -> List[Any]:
        """Transform records based on the defined transforms."""
        transforms = [
            {"field": "new_description", "expression": "{hostname.upper().replace('.', '-')}"},
        ]
        for record in records:
            apply_transforms(record, transforms)
        return records
