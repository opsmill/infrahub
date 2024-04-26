from dataclasses import dataclass


@dataclass
class IpamNodeDetails:
    node_uuid: str
    is_address: bool
    namespace_id: str
    ip_value: str
