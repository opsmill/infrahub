from dataclasses import dataclass
from ipaddress import IPv4Interface, IPv6Interface, ip_interface

import pytest

from infrahub.graphql.mutations.ipam import get_ip_address_lock_names


@dataclass
class LockNamesCase:
    name: str
    addresses: list[tuple[str, IPv4Interface | IPv6Interface]]
    expected: list[str]


@pytest.mark.parametrize(
    "case",
    [
        LockNamesCase(
            name="different-addresses-in-one-namespace",
            addresses=[("ns1", ip_interface("10.0.0.2/24")), ("ns1", ip_interface("10.0.0.1/24"))],
            expected=[
                "global.object.BuiltinIPAddress_ns1_10.0.0.1",
                "global.object.BuiltinIPAddress_ns1_10.0.0.2",
            ],
        ),
        LockNamesCase(
            name="one-host-with-two-prefix-lengths",
            addresses=[("ns1", ip_interface("10.0.0.1/24")), ("ns1", ip_interface("10.0.0.1/32"))],
            expected=["global.object.BuiltinIPAddress_ns1_10.0.0.1"],
        ),
        LockNamesCase(
            name="one-address-in-two-namespaces",
            addresses=[("ns2", ip_interface("10.0.0.1/24")), ("ns1", ip_interface("10.0.0.1/24"))],
            expected=[
                "global.object.BuiltinIPAddress_ns1_10.0.0.1",
                "global.object.BuiltinIPAddress_ns2_10.0.0.1",
            ],
        ),
        LockNamesCase(
            name="ipv6-address",
            addresses=[("ns1", ip_interface("2001:0db8:0000::0001/64"))],
            expected=["global.object.BuiltinIPAddress_ns1_2001:db8::1"],
        ),
    ],
    ids=lambda case: case.name,
)
def test_ip_address_lock_names_cover_one_address_value(case: LockNamesCase) -> None:
    assert get_ip_address_lock_names(case.addresses) == case.expected
