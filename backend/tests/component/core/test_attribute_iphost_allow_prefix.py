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
from uuid import uuid4

import pytest

from infrahub.core import registry
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.model.path import BranchTrackingId, EnrichedDiffConflict
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.constraints.attribute_uniqueness import NodeAttributeUniquenessConstraint
from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import IPHostAttributeParameters, TextAttributeParameters
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import UniquenessViolationError, ValidationError
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.pools.noop_allocator import NoOpPoolAllocator
from infrahub.profiles.node_applier import NodeProfilesApplier
from infrahub.templates.node_applier import NodeTemplateApplier
from tests.helpers.graphql import graphql
from tests.helpers.schema import load_schema
from tests.helpers.schema.dns_delegation import DNS_DELEGATION_SCHEMA
from tests.helpers.schema.dns_record import DNS_RECORD_DEFINITION

if TYPE_CHECKING:
    from graphql import ExecutionResult

    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import EnrichedDiffNode
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


DNS_RECORD_KIND = "TestingDnsRecord"
DNS_RECORD_PROFILE_KIND = "ProfileTestingDnsRecord"
DNS_RECORD_TEMPLATE_KIND = "TemplateTestingDnsRecord"

DNS_ZONE_KIND = "TestingDnsZone"
DECLARED_DELEGATION_KIND = "TestingDeclaredDelegation"
UNDECLARED_DELEGATION_KIND = "TestingUndeclaredDelegation"
ZONE_ROOT_KIND = "TestingZoneRoot"
ZONE_LEAF_KIND = "TestingZoneLeaf"
ZONE_MGMT_LEAF_KIND = "TestingZoneMgmtLeaf"

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

ACTIVE_VALUE_QUERY = """
MATCH (n:Node { uuid: $node_id })-[:HAS_ATTRIBUTE]->(a:Attribute { name: $attribute_name })
MATCH (a)-[e:HAS_VALUE]->(av:AttributeIPHost)
WHERE e.status = "active" AND e.to IS NULL
RETURN av.value AS value
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


async def _set_values(db: InfrahubDatabase, branch: Branch, node_id: str, **values: str) -> None:
    node = await NodeManager.get_one(db=db, branch=branch, id=node_id, raise_on_error=True)
    for name, value in values.items():
        node.get_attribute(name).value = value
    await node.save(db=db)


async def _branch_diff_node(db: InfrahubDatabase, branch: Branch, node_id: str) -> EnrichedDiffNode:
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    await diff_coordinator.update_branch_diff(base_branch=registry.get_branch_from_registry(), diff_branch=branch)
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    diff = await diff_repository.get_one(tracking_id=BranchTrackingId(name=branch.name), diff_branch_name=branch.name)
    return next(node for node in diff.nodes if node.uuid == node_id)


def _value_conflict(diff_node: EnrichedDiffNode, attribute_name: str) -> EnrichedDiffConflict | None:
    for attribute in diff_node.attributes:
        if attribute.name != attribute_name:
            continue
        for prop in attribute.properties:
            if prop.property_type is DatabaseEdgeType.HAS_VALUE:
                return prop.conflict
    return None


async def _active_stored_value(db: InfrahubDatabase, node_id: str, attribute_name: str) -> str:
    """Return the value vertex an attribute currently points at, ignoring the ones it used to."""
    records = await db.execute_query(
        query=ACTIVE_VALUE_QUERY, params={"node_id": node_id, "attribute_name": attribute_name}
    )
    assert len(records) == 1
    return records[0]["value"]


async def _matching_ids(db: InfrahubDatabase, branch: Branch, **filters: Any) -> list[str]:
    nodes = await NodeManager.query(db=db, schema=DNS_RECORD_KIND, branch=branch, filters=filters)
    return [node.id for node in nodes]


async def _run_query(db: InfrahubDatabase, branch: Branch, query: str, variables: dict[str, Any]) -> ExecutionResult:
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    return await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )


async def _queried_ids(db: InfrahubDatabase, branch: Branch, query: str, variables: dict[str, Any]) -> list[str]:
    result = await _run_query(db=db, branch=branch, query=query, variables=variables)
    assert result.errors is None
    assert result.data
    return [edge["node"]["id"] for edge in result.data["TestingDnsRecord"]["edges"]]


async def _run_mutation(
    db: InfrahubDatabase, branch: Branch, mutation: str, variables: dict[str, Any]
) -> ExecutionResult:
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    return await graphql(
        schema=gql_params.schema,
        source=mutation,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )


async def _mutation_result(
    db: InfrahubDatabase, branch: Branch, mutation: str, variables: dict[str, Any]
) -> dict[str, Any]:
    result = await _run_mutation(db=db, branch=branch, mutation=mutation, variables=variables)
    assert result.errors is None
    assert result.data
    return result.data["TestingDnsRecordUpdate"]


async def _mutation_errors(db: InfrahubDatabase, branch: Branch, mutation: str, variables: dict[str, Any]) -> list[str]:
    result = await _run_mutation(db=db, branch=branch, mutation=mutation, variables=variables)
    assert result.errors is not None
    return [error.message for error in result.errors]


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


@pytest.fixture
async def dns_record_schema_in_db(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    init_nodes_registry: None,
) -> None:
    """The schema persisted to the graph, so a branch forked from it can be diffed and merged."""
    await load_schema(db=db, schema=_dns_record_root(), update_db=True)


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


class TestTheUpdatePath:
    """An edit of a declared attribute converges on the value a creation of it would have stored.

    Normalising an edit is scoped to a declared attribute on purpose. An attribute that accepts a
    prefix has always kept whatever spelling an edit gave it, and rewriting that would change values
    already in the graph, so the undeclared control here asserts today's behaviour rather than the
    behaviour the declared attribute gets.
    """

    @pytest.fixture
    async def saved_record(self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema: None) -> Node:
        node = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        await node.new(db=db, dns_target="10.0.0.1", v6_target="2001:db8::1", mgmt_ip="10.0.0.1")
        await node.save(db=db)
        return node

    async def test_a_host_masked_edit_reads_back_bare(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        await _set_values(
            db=db,
            branch=default_branch,
            node_id=saved_record.id,
            dns_target="10.0.0.9/32",
            v6_target="2001:db8::9/128",
            mgmt_ip="10.0.0.9",
        )

        reloaded = await NodeManager.get_one(db=db, id=saved_record.id, branch=default_branch, raise_on_error=True)

        assert reloaded.dns_target.value == "10.0.0.9"
        assert reloaded.v6_target.value == "2001:db8::9"
        assert await reloaded.get_display_label(db=db) == "10.0.0.9"
        assert await reloaded.get_hfid(db=db) == ["10.0.0.9"]
        assert reloaded.dns_target.prefixlen == 32
        assert await _active_stored_value(db=db, node_id=saved_record.id, attribute_name="dns_target") == "10.0.0.9"
        assert await _active_stored_value(db=db, node_id=saved_record.id, attribute_name="v6_target") == "2001:db8::9"

        # The undeclared control is untouched: an edit still writes exactly the spelling it was given,
        # so the bare address reaches the graph without the host mask that a creation would have added,
        # and only reading it back puts the mask on.
        assert await _active_stored_value(db=db, node_id=saved_record.id, attribute_name="mgmt_ip") == "10.0.0.9"
        assert reloaded.mgmt_ip.value == "10.0.0.9/32"

    async def test_a_host_masked_edit_through_graphql_reads_back_bare(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        mutation = """
        mutation UpdateRecord($id: String!) {
            TestingDnsRecordUpdate(
                data: {
                    id: $id
                    dns_target: { value: "10.0.0.9/32" }
                    v6_target: { value: "2001:db8::9/128" }
                    mgmt_ip: { value: "10.0.0.9" }
                }
            ) {
                ok
                object {
                    display_label
                    hfid
                    dns_target { value prefixlen }
                    v6_target { value prefixlen }
                    mgmt_ip { value prefixlen }
                }
            }
        }
        """
        result = await _mutation_result(
            db=db, branch=default_branch, mutation=mutation, variables={"id": saved_record.id}
        )

        assert result["ok"] is True
        assert result["object"]["dns_target"] == {"value": "10.0.0.9", "prefixlen": 32}
        assert result["object"]["v6_target"] == {"value": "2001:db8::9", "prefixlen": 128}
        assert result["object"]["display_label"] == "10.0.0.9"
        assert result["object"]["hfid"] == ["10.0.0.9"]
        # The undeclared control answers with the spelling the request used rather than the canonical
        # one a creation would have produced -- the behaviour an edit of it has always had.
        assert result["object"]["mgmt_ip"] == {"value": "10.0.0.9", "prefixlen": 32}

        reloaded = await NodeManager.get_one(db=db, id=saved_record.id, branch=default_branch, raise_on_error=True)
        assert reloaded.dns_target.value == "10.0.0.9"
        assert reloaded.v6_target.value == "2001:db8::9"
        assert await _active_stored_value(db=db, node_id=saved_record.id, attribute_name="dns_target") == "10.0.0.9"
        assert await _active_stored_value(db=db, node_id=saved_record.id, attribute_name="mgmt_ip") == "10.0.0.9"
        assert reloaded.mgmt_ip.value == "10.0.0.9/32"

    async def test_an_edit_to_a_subnet_prefix_is_rejected_and_changes_nothing(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        """Normalising an edit must not turn a rejected prefix into an address that would be accepted."""
        node = await NodeManager.get_one(db=db, id=saved_record.id, branch=default_branch, raise_on_error=True)
        node.dns_target.value = "10.0.0.9/24"
        error = _rejected_for_subnet_prefix("10.0.0.9/24", "dns_target")

        with pytest.raises(ValidationError, match=rf"^{re.escape(error)}$"):
            await node.save(db=db)

        reloaded = await NodeManager.get_one(db=db, id=saved_record.id, branch=default_branch, raise_on_error=True)
        assert reloaded.dns_target.value == "10.0.0.1"
        assert await reloaded.get_display_label(db=db) == "10.0.0.1"

        await _set_values(db=db, branch=default_branch, node_id=saved_record.id, mgmt_ip="10.0.0.9/24")

        control = await NodeManager.get_one(db=db, id=saved_record.id, branch=default_branch, raise_on_error=True)
        assert control.mgmt_ip.value == "10.0.0.9/24"

    async def test_an_edit_onto_a_taken_address_spelled_differently_is_rejected(
        self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema_unique_mgmt_ip: None
    ) -> None:
        """A uniqueness check has to see the value the edit will store, not the spelling it arrived in."""
        taken = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        await taken.new(db=db, dns_target="10.0.0.1", mgmt_ip="10.0.0.1")
        await taken.save(db=db)

        other = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        await other.new(db=db, dns_target="10.0.0.9", mgmt_ip="10.0.0.9/24")
        await other.save(db=db)

        declared_mutation = """
        mutation UpdateRecord($id: String!) {
            TestingDnsRecordUpdate(data: { id: $id, dns_target: { value: "10.0.0.1/32" } }) {
                ok
            }
        }
        """
        declared_error = "Violates uniqueness constraint 'dns_target'"
        errors = await _mutation_errors(
            db=db, branch=default_branch, mutation=declared_mutation, variables={"id": other.id}
        )

        assert errors == [declared_error]

        # The undeclared control compares the spelling the request used against the one in the graph, so
        # a bare address is not seen to collide with the host mask already holding it -- the behaviour it
        # has always had, and the reason normalising an edit stays scoped to the declared attribute.
        undeclared_mutation = """
        mutation UpdateRecord($id: String!) {
            TestingDnsRecordUpdate(data: { id: $id, mgmt_ip: { value: "10.0.0.1" } }) {
                ok
            }
        }
        """
        result = await _mutation_result(
            db=db, branch=default_branch, mutation=undeclared_mutation, variables={"id": other.id}
        )

        assert result["ok"] is True

        reloaded = await NodeManager.get_one(db=db, id=other.id, branch=default_branch, raise_on_error=True)
        assert reloaded.dns_target.value == "10.0.0.9"
        assert await _active_stored_value(db=db, node_id=other.id, attribute_name="mgmt_ip") == "10.0.0.1"
        assert reloaded.mgmt_ip.value == "10.0.0.1/32"


FILTER_BY_TARGET_QUERY = """
query FindRecord($value: String!) {
    TestingDnsRecord(dns_target__value: $value) {
        edges { node { id } }
    }
}
"""

FILTER_BY_MGMT_IP_QUERY = """
query FindRecord($value: String!) {
    TestingDnsRecord(mgmt_ip__value: $value) {
        edges { node { id } }
    }
}
"""

LOOKUP_BY_HFID_QUERY = """
query FindRecord($hfid: [String]!) {
    TestingDnsRecord(hfid: $hfid) {
        edges { node { id } }
    }
}
"""


class TestLookupInput:
    """A value used as lookup input reaches the node that stored it under the other spelling.

    A declared attribute stores one spelling of an address, so a lookup written against the redundant
    host mask has to resolve to it -- otherwise an idempotent upsert written against the masked form
    never finds the node it already created. The undeclared control keeps the lookup behaviour it has
    always had, which is to match only the spelling the graph holds.
    """

    @pytest.fixture
    async def saved_record(self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema: None) -> Node:
        node = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        await node.new(db=db, dns_target="10.0.0.1", v6_target="2001:db8::1", mgmt_ip="10.0.0.1")
        await node.save(db=db)
        return node

    async def test_a_declared_attribute_is_found_by_either_spelling(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        for value in ("10.0.0.1", "10.0.0.1/32"):
            assert await _matching_ids(db=db, branch=default_branch, dns_target__value=value) == [saved_record.id]
            assert (
                await NodeManager.count(
                    db=db, schema=DNS_RECORD_KIND, branch=default_branch, filters={"dns_target__value": value}
                )
                == 1
            )

        for value in ("2001:db8::1", "2001:db8::1/128"):
            assert await _matching_ids(db=db, branch=default_branch, v6_target__value=value) == [saved_record.id]

    async def test_a_declared_attribute_is_found_by_either_spelling_in_a_list_filter(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        assert await _matching_ids(db=db, branch=default_branch, dns_target__values=["10.0.0.1/32"]) == [
            saved_record.id
        ]
        assert await _matching_ids(db=db, branch=default_branch, dns_target__values=["10.0.0.1"]) == [saved_record.id]

    async def test_an_undeclared_attribute_is_found_only_by_the_spelling_it_stored(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        """The control: an attribute that accepts a prefix keeps matching on the stored spelling alone."""
        assert await _matching_ids(db=db, branch=default_branch, mgmt_ip__value="10.0.0.1/32") == [saved_record.id]
        assert await _matching_ids(db=db, branch=default_branch, mgmt_ip__value="10.0.0.1") == []
        assert await _matching_ids(db=db, branch=default_branch, mgmt_ip__values=["10.0.0.1"]) == []

    async def test_a_subnet_prefix_matches_nothing_and_reports_nothing(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        """A prefix a declared attribute can never hold is not rewritten into an address it can.

        A lookup is not a write, so the answer is an empty result rather than an error: rejecting it
        here would make a read fail where it has always simply found nothing.
        """
        assert await _matching_ids(db=db, branch=default_branch, dns_target__value="10.0.0.1/24") == []
        assert await _matching_ids(db=db, branch=default_branch, v6_target__value="2001:db8::1/64") == []
        assert await _matching_ids(db=db, branch=default_branch, mgmt_ip__value="10.0.0.1/24") == []

    async def test_a_value_that_is_not_an_address_matches_nothing_and_reports_nothing(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        assert await _matching_ids(db=db, branch=default_branch, dns_target__value="not-an-address") == []
        assert await _matching_ids(db=db, branch=default_branch, mgmt_ip__value="not-an-address") == []

    async def test_a_graphql_filter_accepts_either_spelling(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        for value in ("10.0.0.1", "10.0.0.1/32"):
            assert await _queried_ids(
                db=db, branch=default_branch, query=FILTER_BY_TARGET_QUERY, variables={"value": value}
            ) == [saved_record.id]

        assert (
            await _queried_ids(
                db=db, branch=default_branch, query=FILTER_BY_TARGET_QUERY, variables={"value": "10.0.0.1/24"}
            )
            == []
        )

        assert await _queried_ids(
            db=db, branch=default_branch, query=FILTER_BY_MGMT_IP_QUERY, variables={"value": "10.0.0.1/32"}
        ) == [saved_record.id]
        assert (
            await _queried_ids(
                db=db, branch=default_branch, query=FILTER_BY_MGMT_IP_QUERY, variables={"value": "10.0.0.1"}
            )
            == []
        )

    async def test_hfid_lookup_accepts_the_returned_hfid_and_the_masked_spelling(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        assert await saved_record.get_hfid(db=db) == ["10.0.0.1"]

        for hfid in (["10.0.0.1"], ["10.0.0.1/32"]):
            found = await NodeManager.get_one_by_hfid(
                db=db, hfid=hfid, kind=DNS_RECORD_KIND, branch=default_branch, raise_on_error=True
            )
            assert found.id == saved_record.id

        assert (
            await NodeManager.get_one_by_hfid(db=db, hfid=["10.0.0.1/24"], kind=DNS_RECORD_KIND, branch=default_branch)
            is None
        )
        assert (
            await NodeManager.get_one_by_hfid(
                db=db, hfid=["not-an-address"], kind=DNS_RECORD_KIND, branch=default_branch
            )
            is None
        )

    async def test_a_graphql_hfid_lookup_accepts_either_spelling(
        self, db: InfrahubDatabase, default_branch: Branch, saved_record: Node
    ) -> None:
        for hfid in (["10.0.0.1"], ["10.0.0.1/32"]):
            assert await _queried_ids(
                db=db, branch=default_branch, query=LOOKUP_BY_HFID_QUERY, variables={"hfid": hfid}
            ) == [saved_record.id]

        assert (
            await _queried_ids(
                db=db, branch=default_branch, query=LOOKUP_BY_HFID_QUERY, variables={"hfid": ["10.0.0.1/24"]}
            )
            == []
        )


@dataclass(frozen=True)
class DelegationRecords:
    zone: Node
    declared: Node
    undeclared: Node


@dataclass(frozen=True)
class HierarchyRecords:
    root: Node
    leaf: Node
    mgmt_leaf: Node


class TestLookupInputReachedThroughARelationship:
    """A component of an HFID that reaches an attribute through a relationship is lookup input too.

    The stored HFID of a node holds the peer's value in the spelling the peer keeps it in, so a
    declared attribute reached across a relationship has to accept the redundant host mask exactly as
    it does when it is reached directly. Each declared case is paired with the undeclared control on
    the same peer, which keeps matching only the spelling the graph holds.
    """

    @pytest.fixture
    async def delegation_schema(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        init_nodes_registry: None,
    ) -> None:
        await load_schema(db=db, schema=DNS_DELEGATION_SCHEMA)

    @pytest.fixture
    async def delegations(
        self, db: InfrahubDatabase, default_branch: Branch, delegation_schema: None
    ) -> DelegationRecords:
        zone = await Node.init(db=db, schema=DNS_ZONE_KIND, branch=default_branch)
        await zone.new(db=db, name="primary-zone", zone_target="10.1.1.1", zone_mgmt_ip="10.1.1.2")
        await zone.save(db=db)

        declared = await Node.init(db=db, schema=DECLARED_DELEGATION_KIND, branch=default_branch)
        await declared.new(db=db, label="primary", zone=zone)
        await declared.save(db=db)

        undeclared = await Node.init(db=db, schema=UNDECLARED_DELEGATION_KIND, branch=default_branch)
        await undeclared.new(db=db, label="mgmt", zone=zone)
        await undeclared.save(db=db)

        return DelegationRecords(zone=zone, declared=declared, undeclared=undeclared)

    @pytest.fixture
    async def hierarchy(
        self, db: InfrahubDatabase, default_branch: Branch, delegation_schema: None
    ) -> HierarchyRecords:
        root = await Node.init(db=db, schema=ZONE_ROOT_KIND, branch=default_branch)
        await root.new(db=db, name="tree-root", tree_target="10.2.2.1", tree_mgmt_ip="10.2.2.2")
        await root.save(db=db)

        leaf = await Node.init(db=db, schema=ZONE_LEAF_KIND, branch=default_branch)
        await leaf.new(db=db, name="tree-leaf", tree_target="10.2.2.3", tree_mgmt_ip="10.2.2.4", parent=root)
        await leaf.save(db=db)

        mgmt_leaf = await Node.init(db=db, schema=ZONE_MGMT_LEAF_KIND, branch=default_branch)
        await mgmt_leaf.new(db=db, name="tree-mgmt-leaf", tree_target="10.2.2.5", tree_mgmt_ip="10.2.2.6", parent=root)
        await mgmt_leaf.save(db=db)

        return HierarchyRecords(root=root, leaf=leaf, mgmt_leaf=mgmt_leaf)

    async def test_a_declared_attribute_reached_through_a_relationship_is_found_by_either_spelling(
        self, db: InfrahubDatabase, default_branch: Branch, delegations: DelegationRecords
    ) -> None:
        assert await delegations.declared.get_hfid(db=db) == ["10.1.1.1", "primary"]

        for hfid in (["10.1.1.1", "primary"], ["10.1.1.1/32", "primary"]):
            found = await NodeManager.get_one_by_hfid(
                db=db, hfid=hfid, kind=DECLARED_DELEGATION_KIND, branch=default_branch, raise_on_error=True
            )
            assert found.id == delegations.declared.id

        assert (
            await NodeManager.get_one_by_hfid(
                db=db, hfid=["10.1.1.1/24", "primary"], kind=DECLARED_DELEGATION_KIND, branch=default_branch
            )
            is None
        )

    async def test_an_undeclared_attribute_reached_through_a_relationship_is_found_only_by_the_stored_spelling(
        self, db: InfrahubDatabase, default_branch: Branch, delegations: DelegationRecords
    ) -> None:
        """The control: reaching an attribute that accepts a prefix across a relationship changes nothing."""
        assert await delegations.undeclared.get_hfid(db=db) == ["10.1.1.2/32", "mgmt"]

        found = await NodeManager.get_one_by_hfid(
            db=db,
            hfid=["10.1.1.2/32", "mgmt"],
            kind=UNDECLARED_DELEGATION_KIND,
            branch=default_branch,
            raise_on_error=True,
        )
        assert found.id == delegations.undeclared.id

        assert (
            await NodeManager.get_one_by_hfid(
                db=db, hfid=["10.1.1.2", "mgmt"], kind=UNDECLARED_DELEGATION_KIND, branch=default_branch
            )
            is None
        )

    async def test_a_component_that_is_not_an_address_still_has_to_match(
        self, db: InfrahubDatabase, default_branch: Branch, delegations: DelegationRecords
    ) -> None:
        """The `Text` component of the same HFID is handed on untouched, so it goes on discriminating."""
        assert (
            await NodeManager.get_one_by_hfid(
                db=db, hfid=["10.1.1.1/32", "secondary"], kind=DECLARED_DELEGATION_KIND, branch=default_branch
            )
            is None
        )
        assert (
            await NodeManager.get_one_by_hfid(
                db=db, hfid=["10.1.1.1", "secondary"], kind=DECLARED_DELEGATION_KIND, branch=default_branch
            )
            is None
        )

    async def test_a_declared_attribute_reached_through_a_parent_is_found_by_either_spelling(
        self, db: InfrahubDatabase, default_branch: Branch, hierarchy: HierarchyRecords
    ) -> None:
        assert await hierarchy.leaf.get_hfid(db=db) == ["10.2.2.1", "tree-leaf"]

        for hfid in (["10.2.2.1", "tree-leaf"], ["10.2.2.1/32", "tree-leaf"]):
            found = await NodeManager.get_one_by_hfid(
                db=db, hfid=hfid, kind=ZONE_LEAF_KIND, branch=default_branch, raise_on_error=True
            )
            assert found.id == hierarchy.leaf.id

        assert (
            await NodeManager.get_one_by_hfid(
                db=db, hfid=["10.2.2.1/24", "tree-leaf"], kind=ZONE_LEAF_KIND, branch=default_branch
            )
            is None
        )

    async def test_an_undeclared_attribute_reached_through_a_parent_is_found_only_by_the_stored_spelling(
        self, db: InfrahubDatabase, default_branch: Branch, hierarchy: HierarchyRecords
    ) -> None:
        assert await hierarchy.mgmt_leaf.get_hfid(db=db) == ["10.2.2.2/32", "tree-mgmt-leaf"]

        found = await NodeManager.get_one_by_hfid(
            db=db,
            hfid=["10.2.2.2/32", "tree-mgmt-leaf"],
            kind=ZONE_MGMT_LEAF_KIND,
            branch=default_branch,
            raise_on_error=True,
        )
        assert found.id == hierarchy.mgmt_leaf.id

        assert (
            await NodeManager.get_one_by_hfid(
                db=db, hfid=["10.2.2.2", "tree-mgmt-leaf"], kind=ZONE_MGMT_LEAF_KIND, branch=default_branch
            )
            is None
        )

    async def test_a_path_that_cannot_be_resolved_leaves_its_component_alone(
        self, db: InfrahubDatabase, default_branch: Branch, delegations: DelegationRecords
    ) -> None:
        """A lookup keeps finding what the graph holds when a path cannot be resolved to an attribute.

        Resolving a path is best-effort here: an HFID path is validated when the schema is loaded, so a
        path that cannot be resolved means the schema and the values in the graph already disagree, and
        a read of it has always answered with whatever the stored HFID matches rather than failing.
        """
        broken = db.schema.get(name=DECLARED_DELEGATION_KIND, branch=default_branch, duplicate=True)
        broken.human_friendly_id = ["zone__no_such_attribute__value", "label__value"]
        db.schema.set(name=DECLARED_DELEGATION_KIND, schema=broken, branch=default_branch.name)

        found = await NodeManager.get_one_by_hfid(
            db=db,
            hfid=["10.1.1.1", "primary"],
            kind=DECLARED_DELEGATION_KIND,
            branch=default_branch,
            raise_on_error=True,
        )
        assert found.id == delegations.declared.id

        assert (
            await NodeManager.get_one_by_hfid(
                db=db, hfid=["10.1.1.1/32", "primary"], kind=DECLARED_DELEGATION_KIND, branch=default_branch
            )
            is None
        )


class TestGeneratedKindsInheritTheDeclaration:
    """The generated profile and object-template kinds behave like the kind they are derived from.

    A declaration lost on either path would be invisible: the node kind would keep storing bare
    addresses, so the feature would still look like it works while every value that reached a node
    through a profile or a template carried a mask.

    `dns_target` is absent from both generated kinds because unique attributes are excluded from them,
    so `v6_target` is the declared attribute under test and `mgmt_ip` remains the undeclared control.
    """

    async def test_the_declaration_reaches_the_generated_kinds(
        self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema: None
    ) -> None:
        for kind in (DNS_RECORD_KIND, DNS_RECORD_PROFILE_KIND, DNS_RECORD_TEMPLATE_KIND):
            schema = registry.schema.get(name=kind, branch=default_branch, duplicate=False)

            assert schema.get_attribute("v6_target").parameters == IPHostAttributeParameters(allow_prefix=False)
            assert schema.get_attribute("mgmt_ip").parameters == IPHostAttributeParameters(allow_prefix=True)

    async def test_a_profile_validates_and_normalises_like_a_node(
        self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema: None
    ) -> None:
        rejected = await Node.init(db=db, schema=DNS_RECORD_PROFILE_KIND, branch=default_branch)
        error = _rejected_for_subnet_prefix("2001:db8::1/64", "v6_target")

        with pytest.raises(ValidationError, match=rf"^{re.escape(error)}$"):
            await rejected.new(db=db, profile_name="rejected", profile_priority=1000, v6_target="2001:db8::1/64")

        profile = await Node.init(db=db, schema=DNS_RECORD_PROFILE_KIND, branch=default_branch)
        await profile.new(
            db=db,
            profile_name="accepted",
            profile_priority=1000,
            v6_target="2001:db8::1/128",
            mgmt_ip="10.0.0.1",
        )
        await profile.save(db=db)

        reloaded = await NodeManager.get_one(db=db, id=profile.id, branch=default_branch, raise_on_error=True)
        assert reloaded.v6_target.value == "2001:db8::1"
        assert reloaded.mgmt_ip.value == "10.0.0.1/32"

    async def test_a_node_receives_the_bare_value_from_its_profile(
        self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema: None
    ) -> None:
        profile = await Node.init(db=db, schema=DNS_RECORD_PROFILE_KIND, branch=default_branch)
        await profile.new(
            db=db,
            profile_name="dns-defaults",
            profile_priority=1000,
            v6_target="2001:db8::1/128",
            mgmt_ip="10.0.0.1",
        )
        await profile.save(db=db)

        node = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        await node.new(db=db, dns_target=FILLER_TARGET)
        await node.save(db=db)
        await node.profiles.update(db=db, data=[profile])
        await node.save(db=db)

        applier = NodeProfilesApplier(db=db, branch=default_branch)
        assert sorted(await applier.apply_profiles(node=node)) == ["mgmt_ip", "v6_target"]
        await node.save(db=db)

        reloaded = await NodeManager.get_one(db=db, id=node.id, branch=default_branch, raise_on_error=True)
        assert reloaded.v6_target.value == "2001:db8::1"
        assert reloaded.mgmt_ip.value == "10.0.0.1/32"

    async def test_a_template_validates_and_normalises_like_a_node(
        self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema: None
    ) -> None:
        template_schema = registry.schema.get_template_schema(name=DNS_RECORD_TEMPLATE_KIND, branch=default_branch)
        rejected = await Node.init(db=db, schema=template_schema, branch=default_branch)
        error = _rejected_for_subnet_prefix("2001:db8::1/64", "v6_target")

        with pytest.raises(ValidationError, match=rf"^{re.escape(error)}$"):
            await rejected.new(db=db, template_name="rejected", v6_target="2001:db8::1/64")

        template = await Node.init(db=db, schema=template_schema, branch=default_branch)
        await template.new(db=db, template_name="accepted", v6_target="2001:db8::1/128", mgmt_ip="10.0.0.1")
        await template.save(db=db)

        reloaded = await NodeManager.get_one(db=db, id=template.id, branch=default_branch, raise_on_error=True)
        assert reloaded.v6_target.value == "2001:db8::1"
        assert reloaded.mgmt_ip.value == "10.0.0.1/32"

    async def test_a_node_receives_the_bare_value_from_its_template(
        self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema: None
    ) -> None:
        template_schema = registry.schema.get_template_schema(name=DNS_RECORD_TEMPLATE_KIND, branch=default_branch)
        template = await Node.init(db=db, schema=template_schema, branch=default_branch)
        await template.new(db=db, template_name="dns-defaults", v6_target="2001:db8::1/128", mgmt_ip="10.0.0.1")
        await template.save(db=db)

        applier = NodeTemplateApplier(db=db, branch=default_branch, pool_allocator=NoOpPoolAllocator())
        fields = await applier.apply(
            template=template,
            target_schema=registry.schema.get_node_schema(name=DNS_RECORD_KIND, branch=default_branch),
            target_id=str(uuid4()),
            user_fields={"dns_target": FILLER_TARGET},
        )

        assert fields["v6_target"]["value"] == "2001:db8::1"
        assert fields["mgmt_ip"]["value"] == "10.0.0.1/32"

        node = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        await node.new(db=db, **fields)
        await node.save(db=db)

        reloaded = await NodeManager.get_one(db=db, id=node.id, branch=default_branch, raise_on_error=True)
        assert reloaded.v6_target.value == "2001:db8::1"
        assert reloaded.mgmt_ip.value == "10.0.0.1/32"


class TestBranchMerge:
    async def test_the_declaration_and_its_rejection_survive_a_schema_merge(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        init_nodes_registry: None,
    ) -> None:
        """A declaration authored on a branch keeps working once it reaches the target branch."""
        branch = await create_branch(db=db, branch_name="declare-bare-addresses")
        await load_schema(db=db, schema=_dns_record_root(), branch_name=branch.name, update_db=True)

        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
        await diff_merger.merge_graph(at=Timestamp())

        merged_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        registry.schema.set_schema_branch(name=default_branch.name, schema=merged_schema)
        merged_record = merged_schema.get(name=DNS_RECORD_KIND, duplicate=False)

        assert merged_record.get_attribute("dns_target").parameters == IPHostAttributeParameters(allow_prefix=False)
        assert merged_record.get_attribute("v6_target").parameters == IPHostAttributeParameters(allow_prefix=False)
        assert merged_record.get_attribute("mgmt_ip").parameters == IPHostAttributeParameters(allow_prefix=True)

        rejected = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        error = _rejected_for_subnet_prefix("10.0.0.1/24", "dns_target")

        with pytest.raises(ValidationError, match=rf"^{re.escape(error)}$"):
            await rejected.new(db=db, dns_target="10.0.0.1/24")

        accepted = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        await accepted.new(db=db, dns_target="10.0.0.1/32", mgmt_ip="10.0.0.1/24")
        await accepted.save(db=db)

        reloaded = await NodeManager.get_one(db=db, id=accepted.id, branch=default_branch, raise_on_error=True)
        assert reloaded.dns_target.value == "10.0.0.1"
        assert reloaded.mgmt_ip.value == "10.0.0.1/24"

    async def test_divergent_edits_on_either_flavour_still_conflict(
        self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema_in_db: None
    ) -> None:
        """Two branches picking genuinely different addresses conflict, declared attribute or not.

        This is the floor the convergence expectation is measured against: without it, a reported
        absence of conflict could just as well mean the diff never looked at the attribute.
        """
        record = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        await record.new(db=db, dns_target="10.0.0.100", mgmt_ip="10.0.0.100")
        await record.save(db=db)

        branch = await create_branch(db=db, branch_name="divergent-addresses")
        await _set_values(db=db, branch=branch, node_id=record.id, dns_target="10.0.0.2", mgmt_ip="10.0.0.2/24")
        await _set_values(db=db, branch=default_branch, node_id=record.id, dns_target="10.0.0.3", mgmt_ip="10.0.0.3/24")

        diff_node = await _branch_diff_node(db=db, branch=branch, node_id=record.id)

        assert _value_conflict(diff_node, "dns_target") is not None
        assert _value_conflict(diff_node, "mgmt_ip") is not None

    async def test_input_forms_that_converge_on_one_value_do_not_conflict(
        self, db: InfrahubDatabase, default_branch: Branch, dns_record_schema_in_db: None
    ) -> None:
        """Bare and host-masked edits of a declared attribute are the same edit, so a merge sees no conflict.

        The undeclared control is the same shape one prefix apart: there a bare address and a host mask
        also mean the same thing, while a real subnet prefix does not, so only the declared attribute
        can converge on a value the other side spelled differently.
        """
        record = await Node.init(db=db, schema=DNS_RECORD_KIND, branch=default_branch)
        await record.new(db=db, dns_target="10.0.0.100", mgmt_ip="10.0.0.100")
        await record.save(db=db)

        branch = await create_branch(db=db, branch_name="converging-addresses")
        await _set_values(db=db, branch=branch, node_id=record.id, dns_target="10.0.0.1", mgmt_ip="10.0.0.1")
        await _set_values(
            db=db, branch=default_branch, node_id=record.id, dns_target="10.0.0.1/32", mgmt_ip="10.0.0.1/24"
        )

        diff_node = await _branch_diff_node(db=db, branch=branch, node_id=record.id)

        assert _value_conflict(diff_node, "dns_target") is None
        assert _value_conflict(diff_node, "mgmt_ip") is not None


class TestAttributeKindChange:
    """Today a declaration is dropped without a word when the attribute stops being an `IPHost`.

    The parameters of an attribute are re-typed from its kind, and fields the target kind does not know
    about are discarded. That silence is accepted for now; these assertions exist so that changing it
    is a deliberate act rather than an accident.
    """

    def test_leaving_iphost_drops_the_declaration_from_a_schema_payload(self) -> None:
        declared = _dns_record_root().nodes[0].get_attribute("dns_target")
        assert declared.parameters == IPHostAttributeParameters(allow_prefix=False)

        retyped = _dns_record_root(dns_target={"kind": "Text"}).nodes[0].get_attribute("dns_target")

        assert retyped.parameters == TextAttributeParameters()

    def test_leaving_iphost_drops_the_declaration_from_a_loaded_schema(self) -> None:
        declared = _dns_record_root().nodes[0].get_attribute("dns_target")

        retyped = AttributeSchema(name=declared.name, kind="Text", parameters=declared.parameters)

        assert retyped.parameters == TextAttributeParameters()

    def test_returning_to_iphost_restores_the_permissive_default(self) -> None:
        retyped = AttributeSchema(
            name="dns_target", kind="Text", parameters=IPHostAttributeParameters(allow_prefix=False)
        )

        restored = AttributeSchema(name="dns_target", kind="IPHost", parameters=retyped.parameters)

        assert restored.parameters == IPHostAttributeParameters(allow_prefix=True)

    def test_a_change_that_keeps_the_kind_keeps_the_declaration(self) -> None:
        """Pairing the drop with a re-parse that keeps the kind, so the cause is the kind and nothing else."""
        edited = _dns_record_root(dns_target={"description": "The address this record resolves to"}).nodes[0]

        assert edited.get_attribute("dns_target").parameters == IPHostAttributeParameters(allow_prefix=False)
        assert edited.get_attribute("mgmt_ip").parameters == IPHostAttributeParameters(allow_prefix=True)
