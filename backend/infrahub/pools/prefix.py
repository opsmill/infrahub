from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from netaddr import IPSet

    from infrahub.core.ipam.constants import IPNetworkType


def get_next_available_prefix(
    pool: IPSet, prefix_length: int | None = None, prefix_ver: Literal[4, 6] = 4
) -> IPNetworkType:
    """Get the next available prefix of a given prefix length from an IPSet.

    Args:
        pool: netaddr IPSet object with available subnets
        prefix_length: length of the desired prefix
        prefix_ver: IPSet can contain a mix of IPv4 and IPv6 subnets. This parameter specifies the IP version of prefix to acquire.

    Raises:
        ValueError: If there are no available subnets in the pool

    """
    for cidr in pool.iter_cidrs():
        if cidr.version != prefix_ver:
            continue

        if prefix_length is None:
            return cidr

        if cidr.prefixlen <= prefix_length:
            return ipaddress.ip_network(f"{cidr.network}/{prefix_length}")

    raise ValueError("No available subnets in pool")
