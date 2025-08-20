import ipaddress
from enum import Enum

IPNetworkType = ipaddress.IPv6Network | ipaddress.IPv4Network
IPAddressType = ipaddress.IPv6Interface | ipaddress.IPv4Interface
AllIPTypes = IPNetworkType | IPAddressType


class PrefixMemberType(Enum):
    PREFIX = "prefix"
    ADDRESS = "address"
