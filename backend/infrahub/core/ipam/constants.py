import ipaddress
from typing import Union

IPNetworkType = Union[ipaddress.IPv6Network, ipaddress.IPv4Network]
IPAddressType = Union[ipaddress.IPv6Interface, ipaddress.IPv4Interface]
AllIPTypes = Union[IPNetworkType, IPAddressType]
