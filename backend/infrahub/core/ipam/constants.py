import ipaddress
from enum import Enum, StrEnum

IPNetworkType = ipaddress.IPv6Network | ipaddress.IPv4Network
IPAddressType = ipaddress.IPv6Interface | ipaddress.IPv4Interface
AllIPTypes = IPNetworkType | IPAddressType


class PrefixMemberType(Enum):
    PREFIX = "prefix"
    ADDRESS = "address"


class AnyBranch(StrEnum):
    """Scope of an IPAM read that counts a value as held while any live branch holds it."""

    ANY_BRANCH = "any_branch"


ANY_BRANCH = AnyBranch.ANY_BRANCH
