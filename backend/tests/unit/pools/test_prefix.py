import ipaddress

import pytest
from netaddr import IPSet

from infrahub.pools.prefix import get_next_available_prefix, get_prefix_type


def test_get_prefix_type_v4():
    """Tests getting an IP prefix type of ipv4."""
    prefix_type = get_prefix_type("192.0.2.0/24")
    assert prefix_type == "ipv4"


def test_get_prefix_type_v6():
    """Tests getting an IP prefix type of ipv6."""
    prefix_type = get_prefix_type("2001:db8::/32")
    assert prefix_type == "ipv6"


def test_get_prefix_type_invalid():
    """Tests getting an invalid IP prefix type."""
    with pytest.raises(ValueError):
        get_prefix_type("invalid_prefix")


def test_get_next_available_prefix_v4():
    """Tests getting the next available IPv4 prefix."""
    pool = IPSet(["192.0.2.0/24"])
    pool.remove("192.0.2.0/30")
    next_prefix = get_next_available_prefix(pool, 30, "ipv4")
    assert next_prefix == ipaddress.IPv4Network("192.0.2.4/30")


def test_get_next_available_prefix_v6():
    """Tests getting the next available IPv6 prefix."""
    pool = IPSet(["2001:db8::/32"])
    pool.remove("2001:db8::/64")
    next_prefix = get_next_available_prefix(pool, 64, "ipv6")
    assert next_prefix == ipaddress.IPv6Network("2001:db8:0:1::/64")


def test_get_next_available_prefix_mixed():
    """Tests getting the next available prefix from a mixed pool."""
    pool = IPSet(["2001:db8::/32", "192.0.2.0/24"])
    next_prefix = get_next_available_prefix(pool, 30, "ipv4")
    assert next_prefix == ipaddress.IPv4Network("192.0.2.0/30")

    pool = IPSet(["192.0.2.0/24", "2001:db8::/32"])
    next_prefix = get_next_available_prefix(pool, 64, "ipv6")
    assert next_prefix == ipaddress.IPv6Network("2001:db8::/64")


def test_get_next_available_prefix_exhausted_v4_pool():
    """Tests getting the next available prefix from an exhausted IPv4 pool."""
    pool = IPSet(["192.0.2.0/24"])
    with pytest.raises(ValueError):
        get_next_available_prefix(pool, 23, "ipv4")


def test_get_next_available_prefix_exhausted_v6_pool():
    """Tests getting the next available prefix from an exhausted IPv6 pool."""
    pool = IPSet(["2001:db8::/32"])
    with pytest.raises(ValueError):
        get_next_available_prefix(pool, 30, "ipv6")
