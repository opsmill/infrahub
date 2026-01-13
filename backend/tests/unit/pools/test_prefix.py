import ipaddress

import pytest
from netaddr import IPSet

from infrahub.pools.prefix import get_next_available_prefix


def test_get_next_available_prefix_v4() -> None:
    """Tests getting the next available IPv4 prefix."""
    pool = IPSet(["192.0.2.0/24"])
    pool.remove("192.0.2.0/30")
    next_prefix = get_next_available_prefix(pool, 30, 4)
    assert next_prefix == ipaddress.IPv4Network("192.0.2.4/30")


def test_get_next_available_prefix_v6() -> None:
    """Tests getting the next available IPv6 prefix."""
    pool = IPSet(["2001:db8::/32"])
    pool.remove("2001:db8::/64")
    next_prefix = get_next_available_prefix(pool, 64, 6)
    assert next_prefix == ipaddress.IPv6Network("2001:db8:0:1::/64")


def test_get_next_available_prefix_mixed() -> None:
    """Tests getting the next available prefix from a mixed pool."""
    pool = IPSet(["2001:db8::/32", "192.0.2.0/24"])
    next_prefix = get_next_available_prefix(pool, 30, 4)
    assert next_prefix == ipaddress.IPv4Network("192.0.2.0/30")

    pool = IPSet(["192.0.2.0/24", "2001:db8::/32"])
    next_prefix = get_next_available_prefix(pool, 64, 6)
    assert next_prefix == ipaddress.IPv6Network("2001:db8::/64")


def test_get_next_available_prefix_exhausted_v4_pool() -> None:
    """Tests getting the next available prefix from an exhausted IPv4 pool."""
    pool = IPSet(["192.0.2.0/24"])
    with pytest.raises(ValueError):
        get_next_available_prefix(pool, 23, 4)


def test_get_next_available_prefix_exhausted_v6_pool() -> None:
    """Tests getting the next available prefix from an exhausted IPv6 pool."""
    pool = IPSet(["2001:db8::/32"])
    with pytest.raises(ValueError):
        get_next_available_prefix(pool, 30, 6)
