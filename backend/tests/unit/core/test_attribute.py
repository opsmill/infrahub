import re
from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.attribute import Integer, IPAddress, IPAddressOptional, IPHost, PayloadPresence
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ValidationError


@pytest.fixture
def branch() -> Branch:
    return Branch(name="main")


@pytest.fixture
def ipaddress_schema() -> AttributeSchema:
    return AttributeSchema(name="addr", kind="IPAddress")


def build_attribute(
    schema: AttributeSchema,
    branch: Branch,
    data: str | None,
    attribute_class: type[IPAddress] = IPAddress,
) -> IPAddress:
    at = Timestamp()
    node_schema = NodeSchema(name="DnsRecord", namespace="Test", attributes=[schema])
    node = Node(schema=node_schema, branch=branch, at=at)

    return attribute_class(name=schema.name, schema=schema, branch=branch, at=at, node=node, data=data)


@pytest.mark.parametrize(
    "input_value",
    [
        "10.0.0.1",
        "255.255.255.255",
        "0.0.0.0",  # noqa: S104
        "2001:db8::1",
        "::1",
        "::ffff:10.0.0.1",
    ],
)
def test_validate_format_ipaddress_accepts_bare_address(
    branch: Branch, ipaddress_schema: AttributeSchema, input_value: str
) -> None:
    build_attribute(schema=ipaddress_schema, branch=branch, data=input_value)


@pytest.mark.parametrize(
    "input_value",
    [
        "10.0.0.1/32",
        "10.0.0.1/24",
        "10.0.0.0/255.255.255.0",
        "2001:db8::1/128",
        "2001:db8::/64",
        "010.0.0.1",
        "10.0.0.256",
        "10.0.1",
        "not-an-ip",
        "",
    ],
)
def test_validate_format_ipaddress_rejects_prefix_and_garbage(
    branch: Branch, ipaddress_schema: AttributeSchema, input_value: str
) -> None:
    with pytest.raises(ValidationError, match=rf"^{re.escape(input_value)} is not a valid IPAddress at addr$"):
        build_attribute(schema=ipaddress_schema, branch=branch, data=input_value)


def test_validate_ipaddress_returns(branch: Branch, ipaddress_schema: AttributeSchema) -> None:
    test_ipv4 = build_attribute(schema=ipaddress_schema, branch=branch, data="10.0.2.1")
    test_ipv6 = build_attribute(schema=ipaddress_schema, branch=branch, data="2001:db8::1")

    assert test_ipv4.value == "10.0.2.1"
    assert test_ipv4.version == 4
    assert test_ipv4.ip_integer == 167772673
    assert test_ipv4.ip_binary == "00001010000000000000001000000001"
    assert len(test_ipv4.ip_binary) == 32
    assert test_ipv4.to_db() == {
        "binary_address": "00001010000000000000001000000001",
        "is_default": False,
        "prefixlen": 32,
        "value": "10.0.2.1",
        "version": 4,
    }

    assert test_ipv6.value == "2001:db8::1"
    assert test_ipv6.version == 6
    assert test_ipv6.ip_integer == 42540766411282592856903984951653826561
    assert test_ipv6.ip_binary == f"00100000000000010000110110111000{'0' * 95}1"
    assert len(test_ipv6.ip_binary) == 128
    assert test_ipv6.to_db() == {
        "binary_address": f"00100000000000010000110110111000{'0' * 95}1",
        "is_default": False,
        "prefixlen": 128,
        "value": "2001:db8::1",
        "version": 6,
    }


def test_validate_ipaddress_returns_without_value(branch: Branch) -> None:
    schema = AttributeSchema(name="addr", kind="IPAddress", optional=True)

    attr = build_attribute(schema=schema, branch=branch, data=None, attribute_class=IPAddressOptional)

    assert attr.value is None
    assert attr.version is None
    with pytest.raises(ValueError, match=r"^value for IPAddress must be defined$"):
        _ = attr.obj


@pytest.mark.parametrize(
    ("input_value", "normalized_value"),
    [
        ("10.0.0.1", "10.0.0.1"),
        ("2001:db8::1", "2001:db8::1"),
        ("2001:0db8:0000:0000:0000:0000:0000:0001", "2001:db8::1"),
        ("2001:DB8::1", "2001:db8::1"),
        # an IPv4-mapped address keeps its family rather than collapsing to the IPv4 form
        ("::ffff:10.0.0.1", "::ffff:10.0.0.1"),
    ],
)
def test_ipaddress_normalizes_value(input_value: str, normalized_value: str) -> None:
    assert IPAddress._normalize_value(input_value) == normalized_value


def build_iphost_attribute(branch: Branch, data: str) -> IPHost:
    schema = AttributeSchema(name="address", kind="IPHost")
    at = Timestamp()
    node_schema = NodeSchema(name="Host", namespace="Test", attributes=[schema])
    node = Node(schema=node_schema, branch=branch, at=at)
    return IPHost(name=schema.name, schema=schema, branch=branch, at=at, node=node, data=data)


async def test_from_graphql_stores_canonical_iphost_value(branch: Branch) -> None:
    attr = build_iphost_attribute(branch=branch, data="192.0.2.10/32")

    changed = await attr.from_graphql(data={"value": "192.0.2.20"})

    assert changed is True
    assert attr.value == "192.0.2.20/32"


async def test_from_graphql_reports_no_change_for_equivalent_iphost_value(branch: Branch) -> None:
    attr = build_iphost_attribute(branch=branch, data="192.0.2.10/32")

    changed = await attr.from_graphql(data={"value": "192.0.2.10"})

    assert changed is False
    assert attr.value == "192.0.2.10/32"


async def test_from_graphql_rejects_invalid_iphost_value(branch: Branch) -> None:
    attr = build_iphost_attribute(branch=branch, data="192.0.2.10/32")

    with pytest.raises(ValidationError, match=r"^not-an-ip is not a valid IPHost at address$"):
        await attr.from_graphql(data={"value": "not-an-ip"})
    assert attr.value == "192.0.2.10/32"


@dataclass(frozen=True)
class PayloadPresenceTestCase:
    name: str
    payload: dict[str, Any]
    value_presence: PayloadPresence
    from_pool_presence: PayloadPresence


PAYLOAD_PRESENCE_TEST_CASES = [
    PayloadPresenceTestCase(
        name="both_omitted",
        payload={"is_protected": True},
        value_presence=PayloadPresence.ABSENT,
        from_pool_presence=PayloadPresence.ABSENT,
    ),
    PayloadPresenceTestCase(
        name="value_only",
        payload={"value": 5},
        value_presence=PayloadPresence.SET,
        from_pool_presence=PayloadPresence.ABSENT,
    ),
    PayloadPresenceTestCase(
        name="explicit_nulls",
        payload={"value": None, "from_pool": None},
        value_presence=PayloadPresence.NULL,
        from_pool_presence=PayloadPresence.NULL,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PAYLOAD_PRESENCE_TEST_CASES])
async def test_from_graphql_records_whether_value_and_from_pool_were_sent(
    branch: Branch, test_case: PayloadPresenceTestCase
) -> None:
    schema = AttributeSchema(name="ticket_id", kind="Number", optional=True)
    at = Timestamp()
    node = Node(schema=NodeSchema(name="Ticket", namespace="Test", attributes=[schema]), branch=branch, at=at)
    attr = Integer(name=schema.name, schema=schema, branch=branch, at=at, node=node, data={"value": 3})

    await attr.from_graphql(data=test_case.payload)

    assert attr.value_presence is test_case.value_presence
    assert attr.from_pool_presence is test_case.from_pool_presence
