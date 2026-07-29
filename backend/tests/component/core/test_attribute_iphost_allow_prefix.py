"""Behaviour of an `IPHost` attribute declared to hold a bare address.

Every test here pairs a declared attribute (`allow_prefix: false`) with the undeclared `mgmt_ip`
control, because regressing the pre-existing prefixed behaviour is a worse outcome than failing to
add the new one.
"""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.constraints.attribute_uniqueness import NodeAttributeUniquenessConstraint
from infrahub.core.schema import SchemaRoot
from infrahub.exceptions import UniquenessViolationError, ValidationError
from tests.helpers.schema import load_schema
from tests.helpers.schema.dns_record import DNS_RECORD_DEFINITION

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


DNS_RECORD_KIND = "TestingDnsRecord"

# A valid bare value for the mandatory declared attribute, so a case exercising another attribute is
# not also fighting a missing mandatory value.
FILLER_TARGET = "10.10.10.10"

IPV4_TARGET_BINARY = "00001010" + "00000000" * 2 + "00000001"
IPV6_TARGET_BINARY = "0010000000000001" + "0000110110111000" + "0" * 80 + "0000000000000001"

# The leading bits shared by every address inside 10.0.0.0/8, which is how prefix containment is
# resolved against the value vertex.
IPV4_SLASH_8_BINARY = "00001010"


def _rejected_for_subnet_prefix(value: str, attribute_name: str) -> str:
    return f"{value} is not a valid IPHost because a subnet prefix is not permitted at {attribute_name}"


def _rejected_as_malformed(value: str, attribute_name: str) -> str:
    return f"{value} is not a valid IPHost at {attribute_name}"


VALUE_VERTEX_QUERY = """
MATCH (n:Node { uuid: $node_id })-[:HAS_ATTRIBUTE]->(a:Attribute { name: $attribute_name })
MATCH (a)-[:HAS_VALUE]->(av:AttributeIPHost)
RETURN av.value AS value, av.prefixlen AS prefixlen, av.version AS version,
       av.binary_address AS binary_address
"""

CONTAINMENT_QUERY = """
MATCH (n:TestingDnsRecord)-[:HAS_ATTRIBUTE]->(a:Attribute { name: $attribute_name })
MATCH (a)-[:HAS_VALUE]->(av:AttributeIPHost)
WHERE av.binary_address STARTS WITH $binary_prefix
RETURN DISTINCT n.uuid AS uuid
"""


def _dns_record_root(**attribute_overrides: dict[str, Any]) -> SchemaRoot:
    definition = deepcopy(DNS_RECORD_DEFINITION)
    for attribute_name, overrides in attribute_overrides.items():
        attribute = next(attr for attr in definition["attributes"] if attr["name"] == attribute_name)
        attribute.update(overrides)
    return SchemaRoot(nodes=[definition])


async def _stored_value_properties(db: InfrahubDatabase, node_id: str, attribute_name: str) -> dict[str, Any]:
    records = await db.execute_query(
        query=VALUE_VERTEX_QUERY, params={"node_id": node_id, "attribute_name": attribute_name}
    )
    assert len(records) == 1
    return dict(records[0])


async def _node_ids_within(db: InfrahubDatabase, attribute_name: str, binary_prefix: str) -> set[str]:
    records = await db.execute_query(
        query=CONTAINMENT_QUERY, params={"attribute_name": attribute_name, "binary_prefix": binary_prefix}
    )
    return {record["uuid"] for record in records}


@pytest.fixture
async def dns_record_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    init_nodes_registry: None,
) -> None:
    await load_schema(db=db, schema=_dns_record_root())


@pytest.fixture
async def dns_record_schema_unique_mgmt_ip(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    init_nodes_registry: None,
) -> None:
    """The undeclared control needs its own uniqueness constraint to be comparable to the declared one."""
    await load_schema(db=db, schema=_dns_record_root(mgmt_ip={"unique": True}))


@dataclass
class ValueCase:
    name: str
    attribute: str
    value: str
    stored: str | None = None
    error: str | None = None


DECLARED_IPV4_CASES = [
    ValueCase(name="declared_ipv4_bare_stays_bare", attribute="dns_target", value="10.0.0.1", stored="10.0.0.1"),
    ValueCase(
        name="declared_ipv4_host_mask_is_normalised_away",
        attribute="dns_target",
        value="10.0.0.1/32",
        stored="10.0.0.1",
    ),
    ValueCase(
        name="declared_ipv4_subnet_prefix_is_rejected",
        attribute="dns_target",
        value="10.0.0.1/24",
        error=_rejected_for_subnet_prefix("10.0.0.1/24", "dns_target"),
    ),
    ValueCase(
        name="declared_ipv4_point_to_point_prefix_is_rejected",
        attribute="dns_target",
        value="10.0.0.1/31",
        error=_rejected_for_subnet_prefix("10.0.0.1/31", "dns_target"),
    ),
    ValueCase(
        name="declared_ipv4_zero_prefix_is_rejected",
        attribute="dns_target",
        value="10.0.0.1/0",
        error=_rejected_for_subnet_prefix("10.0.0.1/0", "dns_target"),
    ),
    ValueCase(
        name="declared_ipv4_with_ipv6_host_length_stays_malformed",
        attribute="dns_target",
        value="10.0.0.1/128",
        error=_rejected_as_malformed("10.0.0.1/128", "dns_target"),
    ),
]

DECLARED_IPV6_CASES = [
    ValueCase(name="declared_ipv6_bare_stays_bare", attribute="v6_target", value="2001:db8::1", stored="2001:db8::1"),
    ValueCase(
        name="declared_ipv6_host_mask_is_normalised_away",
        attribute="v6_target",
        value="2001:db8::1/128",
        stored="2001:db8::1",
    ),
    ValueCase(
        name="declared_ipv6_subnet_prefix_is_rejected",
        attribute="v6_target",
        value="2001:db8::1/64",
        error=_rejected_for_subnet_prefix("2001:db8::1/64", "v6_target"),
    ),
    ValueCase(
        name="declared_ipv6_point_to_point_prefix_is_rejected",
        attribute="v6_target",
        value="2001:db8::1/127",
        error=_rejected_for_subnet_prefix("2001:db8::1/127", "v6_target"),
    ),
    ValueCase(
        name="declared_ipv6_with_ipv4_host_length_is_a_subnet_prefix",
        attribute="v6_target",
        value="2001:db8::1/32",
        error=_rejected_for_subnet_prefix("2001:db8::1/32", "v6_target"),
    ),
    ValueCase(
        name="declared_ipv6_zero_prefix_is_rejected",
        attribute="v6_target",
        value="2001:db8::1/0",
        error=_rejected_for_subnet_prefix("2001:db8::1/0", "v6_target"),
    ),
]

UNDECLARED_CASES = [
    ValueCase(name="undeclared_ipv4_bare_gains_host_mask", attribute="mgmt_ip", value="10.0.0.1", stored="10.0.0.1/32"),
    ValueCase(name="undeclared_ipv4_host_mask_is_kept", attribute="mgmt_ip", value="10.0.0.1/32", stored="10.0.0.1/32"),
    ValueCase(
        name="undeclared_ipv4_subnet_prefix_is_kept", attribute="mgmt_ip", value="10.0.0.1/24", stored="10.0.0.1/24"
    ),
    ValueCase(
        name="undeclared_ipv4_point_to_point_prefix_is_kept",
        attribute="mgmt_ip",
        value="10.0.0.1/31",
        stored="10.0.0.1/31",
    ),
    ValueCase(name="undeclared_ipv4_zero_prefix_is_kept", attribute="mgmt_ip", value="10.0.0.1/0", stored="10.0.0.1/0"),
    ValueCase(
        name="undeclared_ipv6_bare_gains_host_mask",
        attribute="mgmt_ip",
        value="2001:db8::1",
        stored="2001:db8::1/128",
    ),
    ValueCase(
        name="undeclared_ipv6_host_mask_is_kept",
        attribute="mgmt_ip",
        value="2001:db8::1/128",
        stored="2001:db8::1/128",
    ),
    ValueCase(
        name="undeclared_ipv6_subnet_prefix_is_kept",
        attribute="mgmt_ip",
        value="2001:db8::1/64",
        stored="2001:db8::1/64",
    ),
    ValueCase(
        name="undeclared_ipv6_point_to_point_prefix_is_kept",
        attribute="mgmt_ip",
        value="2001:db8::1/127",
        stored="2001:db8::1/127",
    ),
    ValueCase(
        name="undeclared_ipv6_with_ipv4_host_length_is_kept",
        attribute="mgmt_ip",
        value="2001:db8::1/32",
        stored="2001:db8::1/32",
    ),
    ValueCase(
        name="undeclared_ipv6_zero_prefix_is_kept",
        attribute="mgmt_ip",
        value="2001:db8::1/0",
        stored="2001:db8::1/0",
    ),
    ValueCase(
        name="undeclared_ipv4_with_ipv6_host_length_stays_malformed",
        attribute="mgmt_ip",
        value="10.0.0.1/128",
        error=_rejected_as_malformed("10.0.0.1/128", "mgmt_ip"),
    ),
]


class TestValueValidationAndNormalisation:
    @pytest.mark.parametrize(
        "case", DECLARED_IPV4_CASES + DECLARED_IPV6_CASES + UNDECLARED_CASES, ids=lambda case: case.name
    )
    async def test_input_form(
        self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema: None, case: ValueCase
    ) -> None:
        fields: dict[str, Any] = {"dns_target": FILLER_TARGET, case.attribute: case.value}
        node = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)

        if case.error is not None:
            with pytest.raises(ValidationError, match=rf"^{re.escape(case.error)}$"):
                await node.new(db=db, **fields)
            return

        await node.new(db=db, **fields)

        assert getattr(node, case.attribute).value == case.stored

    async def test_an_omitted_optional_attribute_holds_no_value(
        self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema: None
    ) -> None:
        node = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)

        await node.new(db=db, dns_target="10.0.0.1")

        assert node.v6_target.value is None
        assert node.mgmt_ip.value is None

    async def test_an_explicit_null_holds_no_value(
        self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema: None
    ) -> None:
        node = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)

        await node.new(db=db, dns_target="10.0.0.1", v6_target=None, mgmt_ip=None)

        assert node.v6_target.value is None
        assert node.mgmt_ip.value is None


class TestStorageAndDerivedProperties:
    @pytest.fixture
    async def saved_record(self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema: None) -> Node:
        node = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        await node.new(db=db, dns_target="10.0.0.1/32", v6_target="2001:db8::1/128", mgmt_ip="10.0.0.1")
        await node.save(db=db)
        return node

    async def test_stored_value_is_bare_and_reads_back_bare(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        reloaded = await NodeManager.get_one(db=db, id=saved_record.id, branch=default_branch, raise_on_error=True)

        assert reloaded.dns_target.value == "10.0.0.1"
        assert reloaded.v6_target.value == "2001:db8::1"
        assert reloaded.mgmt_ip.value == "10.0.0.1/32"

    async def test_declared_value_vertex_keeps_its_derived_properties(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        ipv4 = await _stored_value_properties(db=db, node_id=saved_record.id, attribute_name="dns_target")
        ipv6 = await _stored_value_properties(db=db, node_id=saved_record.id, attribute_name="v6_target")

        assert ipv4 == {
            "value": "10.0.0.1",
            "prefixlen": 32,
            "version": 4,
            "binary_address": IPV4_TARGET_BINARY,
        }
        assert ipv6 == {
            "value": "2001:db8::1",
            "prefixlen": 128,
            "version": 6,
            "binary_address": IPV6_TARGET_BINARY,
        }

    async def test_undeclared_value_vertex_is_unchanged(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        stored = await _stored_value_properties(db=db, node_id=saved_record.id, attribute_name="mgmt_ip")

        assert stored == {
            "value": "10.0.0.1/32",
            "prefixlen": 32,
            "version": 4,
            "binary_address": IPV4_TARGET_BINARY,
        }

    async def test_prefix_containment_still_resolves_a_declared_attribute(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        declared = await _node_ids_within(db=db, attribute_name="dns_target", binary_prefix=IPV4_SLASH_8_BINARY)
        undeclared = await _node_ids_within(db=db, attribute_name="mgmt_ip", binary_prefix=IPV4_SLASH_8_BINARY)

        assert declared == {saved_record.id}
        assert undeclared == {saved_record.id}

    async def test_derived_attribute_properties_report_the_host_length(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        reloaded = await NodeManager.get_one(db=db, id=saved_record.id, branch=default_branch, raise_on_error=True)

        assert reloaded.dns_target.prefixlen == 32
        assert reloaded.dns_target.version == 4
        assert reloaded.dns_target.ip == "10.0.0.1"
        assert reloaded.v6_target.prefixlen == 128
        assert reloaded.v6_target.version == 6
        assert reloaded.v6_target.ip == "2001:db8::1"
        assert reloaded.mgmt_ip.prefixlen == 32
        assert reloaded.mgmt_ip.version == 4


class TestUniquenessAcrossInputForms:
    async def test_bare_and_host_masked_input_collide(
        self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema_unique_mgmt_ip: None
    ) -> None:
        constraint = NodeAttributeUniquenessConstraint(db=db, branch=default_branch)
        existing = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        await existing.new(db=db, dns_target="10.0.0.1", mgmt_ip="10.0.0.1")
        await existing.save(db=db)

        assert existing.dns_target.value == "10.0.0.1"
        assert existing.mgmt_ip.value == "10.0.0.1/32"

        declared_duplicate = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        await declared_duplicate.new(db=db, dns_target="10.0.0.1/32", mgmt_ip="10.0.0.9")
        declared_message = "An object already exist with this value: dns_target: 10.0.0.1 at dns_target"

        with pytest.raises(UniquenessViolationError, match=rf"^{re.escape(declared_message)}$"):
            await constraint.check(declared_duplicate)

        undeclared_duplicate = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        await undeclared_duplicate.new(db=db, dns_target="10.0.0.9", mgmt_ip="10.0.0.1/32")
        undeclared_message = "An object already exist with this value: mgmt_ip: 10.0.0.1/32 at mgmt_ip"

        with pytest.raises(UniquenessViolationError, match=rf"^{re.escape(undeclared_message)}$"):
            await constraint.check(undeclared_duplicate)

    async def test_a_distinct_address_does_not_collide(
        self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema_unique_mgmt_ip: None
    ) -> None:
        constraint = NodeAttributeUniquenessConstraint(db=db, branch=default_branch)
        existing = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        await existing.new(db=db, dns_target="10.0.0.1", mgmt_ip="10.0.0.1")
        await existing.save(db=db)

        other = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        await other.new(db=db, dns_target="10.0.0.2/32", mgmt_ip="10.0.0.2")

        await constraint.check(other)
