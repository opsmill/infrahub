import ipaddress

import pytest

from infrahub.graphql.queries.search import _try_parse_ip_or_prefix


@pytest.mark.parametrize(
    ("query", "expected_type"),
    [
        ("10.1.2.45", ipaddress.IPv4Address),
        ("192.168.1.1", ipaddress.IPv4Address),
        ("0.0.0.0", ipaddress.IPv4Address),  # noqa: S104
        ("255.255.255.255", ipaddress.IPv4Address),
        ("2001:db8::1", ipaddress.IPv6Address),
        ("::1", ipaddress.IPv6Address),
        ("fe80::1", ipaddress.IPv6Address),
        ("2001:0db8:0000:0000:0000:0000:0000:0001", ipaddress.IPv6Address),
        ("10.0.0.0/8", ipaddress.IPv4Network),
        ("10.1.2.0/24", ipaddress.IPv4Network),
        ("192.168.0.0/16", ipaddress.IPv4Network),
        ("10.1.2.45/24", ipaddress.IPv4Network),  # strict=False strips host bits
        ("2001:db8::/32", ipaddress.IPv6Network),
        ("2001:db8::/48", ipaddress.IPv6Network),
        ("::/0", ipaddress.IPv6Network),
    ],
)
def test_try_parse_ip_or_prefix_valid(query: str, expected_type: type) -> None:
    result = _try_parse_ip_or_prefix(query)
    assert result is not None
    assert isinstance(result, expected_type)


@pytest.mark.parametrize(
    "query",
    [
        "10.1.2",
        "10.1",
        "10",
        "router-core-01",
        "hello world",
        "",
        "abc",
        "10.1.2.45.6",
        "999.999.999.999",
        "2001:0db8",
        "not-an-ip",
    ],
)
def test_try_parse_ip_or_prefix_returns_none(query: str) -> None:
    assert _try_parse_ip_or_prefix(query) is None


def test_try_parse_ip_or_prefix_network_strict_false() -> None:
    """Verify that host bits are masked when parsing CIDR notation."""
    result = _try_parse_ip_or_prefix("10.1.2.45/24")
    assert result is not None
    assert isinstance(result, ipaddress.IPv4Network)
    assert str(result) == "10.1.2.0/24"


def test_try_parse_ip_or_prefix_ipv6_non_canonical() -> None:
    """Verify that IPv6 addresses in non-canonical format are parsed correctly."""
    result = _try_parse_ip_or_prefix("2001:0db8:0000:0000:0000:0000:0000:0001")
    assert result is not None
    assert isinstance(result, ipaddress.IPv6Address)
    assert str(result) == "2001:db8::1"
