from typing import Any, List, Optional
import netutils.regex
import netutils.ip

from infrahub_sync.adapters.netbox import NetboxModel

# -------------------------------------------------------
# AUTO-GENERATED FILE, DO NOT MODIFY
#  This file has been generated with the command `infrahub-sync generate`
#  All modifications will be lost the next time you reexecute this command
# -------------------------------------------------------
class CoreStandardGroup(NetboxModel):
    _modelname = "CoreStandardGroup"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class BuiltinTag(NetboxModel):
    _modelname = "BuiltinTag"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraCircuit(NetboxModel):
    _modelname = "InfraCircuit"
    _identifiers = ("circuit_id",)
    _attributes = ("type", "tags", "provider", "vendor_id", "description")
    circuit_id: str
    vendor_id: Optional[str] = None
    description: Optional[str] = None
    type: str
    tags: Optional[List[str]] = []
    provider: str

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class TemplateCircuitType(NetboxModel):
    _modelname = "TemplateCircuitType"
    _identifiers = ("name",)
    _attributes = ("tags", "description")
    description: Optional[str] = None
    name: str
    tags: Optional[List[str]] = []

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraDevice(NetboxModel):
    _modelname = "InfraDevice"
    _identifiers = ("location", "rack", "organization", "name")
    _attributes = ("tags", "model", "role", "serial_number", "asset_tag", "description")
    serial_number: Optional[str] = None
    asset_tag: Optional[str] = None
    description: Optional[str] = None
    name: Optional[str] = None
    tags: Optional[List[str]] = []
    model: str
    location: str
    role: Optional[str] = None
    organization: Optional[str] = None
    rack: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None
    @classmethod
    def filter_records(cls, records: List[Any]) -> List[Any]:
        filtered_records = []
        for record in records:
            include = True
            try:
                field_value = getattr(record, 'name', '') if not isinstance(record, dict) else record.get('name', '')
                field_value = field_value or ""
                if not netutils.regex.regex_search('dmi01', field_value):
                    include = False
            except Exception as e:
                print(f"Error evaluating filter: 'name | netutils.regex.regex_search('dmi01')' with record {record}: {e}")
                include = False
            try:
                field_value = getattr(record, 'name', '') if not isinstance(record, dict) else record.get('name', '')
                field_value = field_value or ""
                if netutils.regex.regex_search('pdu', field_value):
                    include = False
            except Exception as e:
                print(f"Error evaluating filter: 'name | not netutils.regex.regex_search('pdu')' with record {record}: {e}")
                include = False
            if include:
                filtered_records.append(record)
        return filtered_records

class TemplateDeviceType(NetboxModel):
    _modelname = "TemplateDeviceType"
    _identifiers = ("name", "manufacturer")
    _attributes = ("tags", "full_depth", "height", "part_number")
    full_depth: Optional[bool] = None
    height: Optional[int] = None
    name: str
    part_number: Optional[str] = None
    manufacturer: str
    tags: Optional[List[str]] = []

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraInterfaceL2L3(NetboxModel):
    _modelname = "InfraInterfaceL2L3"
    _identifiers = ("device", "name")
    _attributes = ("tagged_vlan", "tags", "l2_mode", "description", "mgmt_only", "mac_address", "interface_type")
    l2_mode: Optional[str] = None
    name: str
    description: Optional[str] = None
    mgmt_only: Optional[bool] = False
    mac_address: Optional[str] = None
    interface_type: Optional[str] = None
    untagged_vlan: Optional[str] = None
    tagged_vlan: Optional[List[str]] = []
    device: str
    tags: Optional[List[str]] = []

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraIPAddress(NetboxModel):
    _modelname = "InfraIPAddress"
    _identifiers = ("address", "vrf")
    _attributes = ("organization", "description")
    address: str
    description: Optional[str] = None
    organization: Optional[str] = None
    vrf: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraProviderNetwork(NetboxModel):
    _modelname = "InfraProviderNetwork"
    _identifiers = ("name",)
    _attributes = ("provider", "tags", "vendor_id", "description")
    vendor_id: Optional[str] = None
    description: Optional[str] = None
    name: str
    provider: str
    tags: Optional[List[str]] = []

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraPrefix(NetboxModel):
    _modelname = "InfraPrefix"
    _identifiers = ("prefix", "vrf")
    _attributes = ("organization", "location", "role", "description")
    prefix: str
    description: Optional[str] = None
    organization: Optional[str] = None
    location: Optional[str] = None
    role: Optional[str] = None
    vrf: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraRack(NetboxModel):
    _modelname = "InfraRack"
    _identifiers = ("name", "location")
    _attributes = ("role", "tags", "height", "serial_number", "asset_tag", "facility_id")
    height: Optional[int] = None
    serial_number: Optional[str] = None
    asset_tag: Optional[str] = None
    facility_id: Optional[str] = None
    name: str
    role: Optional[str] = None
    location: str
    tags: Optional[List[str]] = []

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraRouteTarget(NetboxModel):
    _modelname = "InfraRouteTarget"
    _identifiers = ("name", "organization")
    _attributes = ("description",)
    name: str
    description: Optional[str] = None
    organization: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraVLAN(NetboxModel):
    _modelname = "InfraVLAN"
    _identifiers = ("name", "vlan_id", "location", "vlan_group")
    _attributes = ("organization", "description")
    vlan_id: int
    name: str
    description: Optional[str] = None
    vlan_group: Optional[str] = None
    organization: Optional[str] = None
    location: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class InfraVRF(NetboxModel):
    _modelname = "InfraVRF"
    _identifiers = ("name",)
    _attributes = ("export_rt", "organization", "import_rt", "description", "vrf_rd")
    name: str
    description: Optional[str] = None
    vrf_rd: Optional[str] = None
    export_rt: Optional[List[str]] = []
    organization: Optional[str] = None
    import_rt: Optional[List[str]] = []

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class OrganizationGeneric(NetboxModel):
    _modelname = "OrganizationGeneric"
    _identifiers = ("name",)
    _attributes = ("group", "description")
    name: str
    description: Optional[str] = None
    group: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class RoleGeneric(NetboxModel):
    _modelname = "RoleGeneric"
    _identifiers = ("name",)
    _attributes = ("description",)
    name: str
    description: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None

class LocationGeneric(NetboxModel):
    _modelname = "LocationGeneric"
    _identifiers = ("name",)
    _attributes = ("organization", "tags", "group", "description", "type")
    name: str
    description: Optional[str] = None
    type: str
    organization: Optional[str] = None
    tags: Optional[List[str]] = []
    group: Optional[str] = None

    local_id: Optional[str] = None
    local_data: Optional[Any] = None
