from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, Literal

from netaddr import IPSet

if TYPE_CHECKING:
    from infrahub.core.ipam.constants import IPNetworkType


def get_next_available_prefix(pool: IPSet, prefix_length: int, prefix_ver: Literal[4, 6] = 4) -> IPNetworkType:
    """Get the next available prefix of a given prefix length from an IPSet.

    Args:
        pool: netaddr IPSet object with available subnets
        prefix_length: length of the desired prefix
        prefix_ver: IPSet can contain a mix of IPv4 and IPv6 subnets. This parameter specifies the IP version of prefix to acquire.

    Raises:
        ValueError: If there are no available subnets in the pool
    """
    prefix_ver_map = {
        4: ipaddress.IPv4Network,
        6: ipaddress.IPv6Network,
    }

    filtered_pool = IPSet([])
    for subnet in pool.iter_cidrs():
        if isinstance(ipaddress.ip_network(str(subnet)), prefix_ver_map[prefix_ver]):
            filtered_pool.add(subnet)

    for cidr in filtered_pool.iter_cidrs():
        if cidr.prefixlen <= prefix_length:
            next_available = ipaddress.ip_network(f"{cidr.network}/{prefix_length}")
            return next_available

    raise ValueError("No available subnets in pool")
