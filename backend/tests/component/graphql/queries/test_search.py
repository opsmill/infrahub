from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.queries.search import _collapse_ipv6
from tests.constants import TestKind
from tests.helpers.graphql import graphql
from tests.helpers.schema import CAR_SCHEMA, TICKET, load_schema, save_schema
from tests.helpers.schema.agnostic_retirement import AGNOSTIC_BEACON, BEACON_KIND

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlParams

SEARCH_QUERY = """
query ($search: String!) {
    InfrahubSearchAnywhere(q: $search) {
        count
        edges {
            node {
                id
                kind
            }
        }
    }
}
"""

SEARCH_QUERY_WITH_PARENT_PREFIXES = """
query ($search: String!) {
    InfrahubSearchAnywhere(q: $search) {
        count
        edges {
            node {
                id
                kind
            }
        }
        parent_prefixes {
            node {
                id
                kind
            }
        }
    }
}
"""


async def test_search_ipv6_address_extended_format(
    db: InfrahubDatabase,
    ip_dataset_01: dict[str, Any],
    branch: Branch,
) -> None:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    res_collapsed = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "2001:db8::"},
    )

    res_extended = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "2001:0db8:0000:0000:0000:0000:0000:0000"},
    )

    assert res_extended.data
    assert res_collapsed.data
    assert (
        res_extended.data["InfrahubSearchAnywhere"]["count"]
        == res_collapsed.data["InfrahubSearchAnywhere"]["count"]
        == 2
    )

    assert (
        res_extended.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"]
        == res_collapsed.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"]
    )

    assert (
        res_extended.data["InfrahubSearchAnywhere"]["edges"][1]["node"]["id"]
        == res_collapsed.data["InfrahubSearchAnywhere"]["edges"][1]["node"]["id"]
    )


async def test_search_ipv6_network_extended_format(
    db: InfrahubDatabase,
    ip_dataset_01: dict[str, Any],
    branch: Branch,
) -> None:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    res_collapsed = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "2001:db8::/48"},
    )

    res_extended = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "2001:0db8:0000:0000:0000:0000:0000:0000/48"},
    )

    assert res_extended.data
    assert res_collapsed.data
    assert (
        res_extended.data["InfrahubSearchAnywhere"]["count"]
        == res_collapsed.data["InfrahubSearchAnywhere"]["count"]
        == 1
    )

    assert (
        res_extended.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"]
        == res_collapsed.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"]
    )


async def test_search_ipv6_address_with_prefix_extended_format(
    db: InfrahubDatabase,
    ip_dataset_01: dict[str, Any],
    default_branch: Branch,
) -> None:
    """An IPv6 address stored with a prefix length (host bits set) is found regardless of input compression."""
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)
    address = await Node.init(db=db, schema=address_schema)
    await address.new(
        db=db, address="2001:db8::1/64", ip_prefix=ip_dataset_01["net162"], ip_namespace=ip_dataset_01["ns1"]
    )
    await address.save(db=db)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    res_collapsed = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "2001:db8::1/64"},
    )

    res_extended = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "2001:0db8:0000:0000:0000:0000:0000:0001/64"},
    )

    assert res_collapsed.data
    assert res_extended.data

    collapsed_ids = {e["node"]["id"] for e in res_collapsed.data["InfrahubSearchAnywhere"]["edges"]}
    extended_ids = {e["node"]["id"] for e in res_extended.data["InfrahubSearchAnywhere"]["edges"]}

    assert address.id in collapsed_ids
    assert collapsed_ids == extended_ids


async def test_search_ipv6_partial_address(
    db: InfrahubDatabase,
    ip_dataset_01: dict[str, Any],
    branch: Branch,
) -> None:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    res_two_segments = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "2001:0db8"},
    )

    res_partial_segment_1 = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "2001:0db8:0"},
    )

    res_partial_segment_2 = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "2001:0db8:0000:0"},
    )

    assert res_two_segments.data
    assert res_partial_segment_1.data
    assert res_partial_segment_2.data

    assert (
        res_two_segments.data["InfrahubSearchAnywhere"]["count"]
        == res_partial_segment_1.data["InfrahubSearchAnywhere"]["count"]
        == res_partial_segment_2.data["InfrahubSearchAnywhere"]["count"]
        == 2
    )

    assert (
        res_two_segments.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"]
        == res_partial_segment_1.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"]
        == res_partial_segment_2.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"]
    )


async def test_search_ipv4(
    db: InfrahubDatabase,
    ip_dataset_01: dict[str, Any],
    branch: Branch,
) -> None:
    """This only tests that ipv6 search specific behavior does not break ipv4 search."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    result_address = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "10.0.0.0"},
    )

    result_network = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "10.0.0.0/8"},
    )

    assert result_address.data
    assert result_network.data
    assert (
        result_address.data["InfrahubSearchAnywhere"]["count"]
        == result_network.data["InfrahubSearchAnywhere"]["count"]
        == 1
    )

    assert (
        result_address.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"]
        == result_network.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"]
    )


@pytest.mark.parametrize(
    "query,expected",
    [
        ("2001:0db8:0000:0000:0000:0000:0000:0000/48", "2001:db8::/48"),
        ("2001:0db8:0000:0000:0000:0000:0000:0000", "2001:db8::"),
        ("2001:0db8", "2001:db8"),
        ("2001:0db8:0", "2001:db8"),
        ("2001:0db8:0000", "2001:db8"),
        ("2001:0db8:0000:0", "2001:db8"),
        ("2001:0db8:0000:0000:00", "2001:db8"),
        ("2001:0db8:0000:0001:00", "2001:db8:0:1"),
        ("2001:0db8:0001:0002:00", "2001:db8:1:2"),
        ("2001:0db8:0001:0000:0002:0000:0003", "2001:db8:1:0:2:0:3"),
        ("2a0b:2081:0001:00d3:0000:0000:0000:0001/127", "2a0b:2081:1:d3::1/127"),
        ("2a0b:2081:1:d3::1/127", "2a0b:2081:1:d3::1/127"),
        ("2001:0db8:0000:0000:0000:0000:0000:0001/64", "2001:db8::1/64"),
    ],
)
def test_collapse_ipv6_address_or_network(query: str, expected: str) -> None:
    assert _collapse_ipv6(query) == expected


@pytest.mark.parametrize(
    "query",
    ["invalid", "invalid:case", "2001:invalid", "2001:0db81:0000", "10.0.0.0", "2001:db8:1"],
)
def test_collapse_ipv6_address_or_network_invalid_cases(query: str) -> None:
    with pytest.raises(ValueError):
        _collapse_ipv6(query)


async def _search_with_parent_prefixes(gql_params: GraphqlParams, query: str) -> dict[str, Any]:
    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_PARENT_PREFIXES,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": query},
    )
    assert result.errors is None
    assert result.data
    return result.data["InfrahubSearchAnywhere"]


async def test_search_parent_prefix_ipv4(db: InfrahubDatabase, ip_dataset_01: dict[str, Any], branch: Branch) -> None:
    """IPv4 parent prefix lookup: address ordering, exact match handling, CIDR, non-existent, no-match, multi-namespace."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    # Address lookup with ordering
    data = await _search_with_parent_prefixes(gql_params=gql_params, query="10.10.1.1")
    parent_prefixes = data["parent_prefixes"]
    assert parent_prefixes is not None
    parent_ids = [pp["node"]["id"] for pp in parent_prefixes]
    expected_ids = {
        ip_dataset_01["net143"].id,  # 10.10.1.0/27  (NS1)
        ip_dataset_01["net142"].id,  # 10.10.1.0/24  (NS1)
        ip_dataset_01["net140"].id,  # 10.10.0.0/16  (NS1)
        ip_dataset_01["net240"].id,  # 10.10.0.0/15  (NS2)
        ip_dataset_01["net146"].id,  # 10.0.0.0/8    (NS1)
    }
    assert set(parent_ids) == expected_ids
    # Ordered by specificity: /27 > /24 > /16 > /15 > /8
    assert parent_ids.index(ip_dataset_01["net143"].id) < parent_ids.index(ip_dataset_01["net142"].id)
    assert parent_ids.index(ip_dataset_01["net142"].id) < parent_ids.index(ip_dataset_01["net140"].id)
    assert parent_ids.index(ip_dataset_01["net140"].id) < parent_ids.index(ip_dataset_01["net240"].id)
    assert parent_ids.index(ip_dataset_01["net240"].id) < parent_ids.index(ip_dataset_01["net146"].id)
    for pp in parent_prefixes:
        assert "IPPrefix" in pp["node"]["kind"]

    # Existing IP address in edges, not in parent_prefixes
    edge_ids = [e["node"]["id"] for e in data["edges"]]
    assert ip_dataset_01["address11"].id in edge_ids
    assert ip_dataset_01["address11"].id not in parent_ids

    # Prefix search excludes exact match from parent_prefixes
    data = await _search_with_parent_prefixes(gql_params=gql_params, query="10.10.1.0/24")
    edge_ids = [e["node"]["id"] for e in data["edges"]]
    assert ip_dataset_01["net142"].id in edge_ids
    parent_ids = [pp["node"]["id"] for pp in data["parent_prefixes"]]
    assert ip_dataset_01["net140"].id in parent_ids  # 10.10.0.0/16
    assert ip_dataset_01["net146"].id in parent_ids  # 10.0.0.0/8
    assert ip_dataset_01["net142"].id not in parent_ids  # exact match excluded

    # Non-existent prefix still returns parents
    data = await _search_with_parent_prefixes(gql_params=gql_params, query="10.10.3.0/24")
    parent_ids = {pp["node"]["id"] for pp in data["parent_prefixes"]}
    assert ip_dataset_01["net140"].id in parent_ids  # 10.10.0.0/16  (NS1)
    assert ip_dataset_01["net146"].id in parent_ids  # 10.0.0.0/8    (NS1)
    assert ip_dataset_01["net240"].id in parent_ids  # 10.10.0.0/15  (NS2)

    # --- Valid IP with no matching prefixes returns empty list ---
    data = await _search_with_parent_prefixes(gql_params=gql_params, query="192.168.1.1")
    assert data["parent_prefixes"] == []

    # Multi-namespace: results from all namespaces
    data = await _search_with_parent_prefixes(gql_params=gql_params, query="10.10.0.1")
    parent_ids = {pp["node"]["id"] for pp in data["parent_prefixes"]}
    assert ip_dataset_01["net140"].id in parent_ids  # NS1: 10.10.0.0/16
    assert ip_dataset_01["net146"].id in parent_ids  # NS1: 10.0.0.0/8
    assert ip_dataset_01["net240"].id in parent_ids  # NS2: 10.10.0.0/15
    assert ip_dataset_01["net241"].id in parent_ids  # NS2: 10.10.0.0/24


async def test_search_parent_prefix_ipv6(db: InfrahubDatabase, ip_dataset_01: dict[str, Any], branch: Branch) -> None:
    """IPv6 parent prefix lookup: address, non-canonical normalization, CIDR."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    # Address lookup with ordering
    data = await _search_with_parent_prefixes(gql_params=gql_params, query="2001:db8::1")
    parent_ids = [pp["node"]["id"] for pp in data["parent_prefixes"]]
    assert ip_dataset_01["net162"].id in parent_ids  # 2001:db8::/64
    assert ip_dataset_01["net161"].id in parent_ids  # 2001:db8::/48
    assert parent_ids.index(ip_dataset_01["net162"].id) < parent_ids.index(ip_dataset_01["net161"].id)

    # Non-canonical format produces same results
    data_extended = await _search_with_parent_prefixes(
        gql_params=gql_params, query="2001:0db8:0000:0000:0000:0000:0000:0001"
    )
    extended_ids = {pp["node"]["id"] for pp in data_extended["parent_prefixes"]}
    assert extended_ids == set(parent_ids)

    # CIDR prefix search excludes exact match
    data = await _search_with_parent_prefixes(gql_params=gql_params, query="2001:db8::/64")
    parent_ids = [pp["node"]["id"] for pp in data["parent_prefixes"]]
    assert ip_dataset_01["net161"].id in parent_ids  # 2001:db8::/48
    assert ip_dataset_01["net162"].id not in parent_ids  # exact match excluded


async def test_search_parent_prefix_non_ip_fallback(
    db: InfrahubDatabase, ip_dataset_01: dict[str, Any], branch: Branch
) -> None:
    """Non-IP and partial IP queries return parent_prefixes as null, text search unchanged."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    # Non-IP text returns null parent_prefixes
    data = await _search_with_parent_prefixes(gql_params=gql_params, query="ns1")
    assert data["parent_prefixes"] is None
    assert data["count"] >= 1

    # Partial IP falls back to text search (US3)
    data = await _search_with_parent_prefixes(gql_params=gql_params, query="10.10")
    assert data["parent_prefixes"] is None
    assert data["count"] > 0


async def test_search_parent_prefix_branch_effective_value(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01: dict[str, Any]
) -> None:
    """A prefix whose value is changed on a branch must not appear as a parent for the old value on that branch."""
    # ip_dataset_01 has net143 = 10.10.1.0/27 in NS1 on the default branch.
    # On a new branch, change it to 10.10.2.0/27 (a completely different subnet).
    # Searching for 10.10.1.1 on that branch should NOT return the changed prefix.
    branch = await create_branch(db=db, branch_name="search-branch-effective")

    net143_branch = await NodeManager.get_one(db=db, branch=branch, id=ip_dataset_01["net143"].id)
    net143_branch.prefix.value = "10.10.2.0/27"
    await net143_branch.save(db=db)

    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    # Search for 10.10.1.1 on the branch — net143 (now 10.10.2.0/27) should NOT be a parent
    data = await _search_with_parent_prefixes(gql_params=gql_params, query="10.10.1.1")
    parent_ids = {pp["node"]["id"] for pp in data["parent_prefixes"]}
    assert ip_dataset_01["net143"].id not in parent_ids  # changed to 10.10.2.0/27 on this branch

    # Other parents that still contain 10.10.1.1 should be present
    assert ip_dataset_01["net142"].id in parent_ids  # 10.10.1.0/24  (unchanged)
    assert ip_dataset_01["net140"].id in parent_ids  # 10.10.0.0/16  (unchanged)
    assert ip_dataset_01["net146"].id in parent_ids  # 10.0.0.0/8    (unchanged)

    # Conversely, searching for 10.10.2.1 on the branch should find net143 (now 10.10.2.0/27)
    data = await _search_with_parent_prefixes(gql_params=gql_params, query="10.10.2.1")
    parent_ids = {pp["node"]["id"] for pp in data["parent_prefixes"]}
    assert ip_dataset_01["net143"].id in parent_ids  # 10.10.2.0/27 on this branch

    # On the default branch, 10.10.1.0/27 should still appear as a parent for 10.10.1.1
    default_branch.update_schema_hash()
    gql_params_default = await prepare_graphql_params(db=db, branch=default_branch)
    data = await _search_with_parent_prefixes(gql_params=gql_params_default, query="10.10.1.1")
    parent_ids = {pp["node"]["id"] for pp in data["parent_prefixes"]}
    assert ip_dataset_01["net143"].id in parent_ids  # still 10.10.1.0/27 on default branch


SEARCH_WITH_OPTIONS_QUERY = """
query ($search: String!, $limit: Int, $partialMatch: Boolean, $caseSensitive: Boolean) {
    InfrahubSearchAnywhere(q: $search, limit: $limit, partial_match: $partialMatch, case_sensitive: $caseSensitive) {
        count
        edges {
            node {
                id
                kind
            }
        }
    }
}
"""

DEFAULT_BRANCH_KEY = "main"
UNKNOWN_UUID = "4c7b1f8e-2d3a-4b5c-8d6e-7f8091a2b3c4"

# The human-friendly ID is stored as JSON text, so the ticket ID must not contain any searched text.
SEARCHED_TICKET = deepcopy(TICKET)
SEARCHED_TICKET.attributes.extend(
    [
        AttributeSchema(name="urgent", kind="Boolean", optional=True),
        AttributeSchema(name="settings", kind="JSON", optional=True),
        AttributeSchema(name="tags", kind="List", optional=True, default_value=["stratus", "alto"]),
    ]
)


@dataclass
class SearchDataset:
    ids: dict[str, str] = field(default_factory=dict)
    kinds: dict[str, str] = field(default_factory=dict)
    branches: dict[str, Branch] = field(default_factory=dict)
    times: dict[str, Timestamp] = field(default_factory=dict)

    async def create(
        self, db: InfrahubDatabase, key: str, kind: str, branch: Branch | None = None, **data: Any
    ) -> Node:
        node = await Node.init(db=db, schema=kind, branch=branch)
        await node.new(db=db, **data)
        await node.save(db=db)
        self.ids[key] = node.id
        self.kinds[key] = kind
        return node

    async def update(self, db: InfrahubDatabase, key: str, branch: Branch, **values: Any) -> None:
        node = await NodeManager.get_one(db=db, id=self.ids[key], branch=branch, raise_on_error=True)
        for attribute_name, value in values.items():
            getattr(node, attribute_name).value = value
        await node.save(db=db)

    async def delete(self, db: InfrahubDatabase, key: str, branch: Branch) -> None:
        node = await NodeManager.get_one(db=db, id=self.ids[key], branch=branch, raise_on_error=True)
        await node.delete(db=db)

    def keys(self, edges: list[dict[str, Any]]) -> list[str]:
        keys_by_id = {node_id: key for key, node_id in self.ids.items()}
        return [keys_by_id.get(edge["node"]["id"], edge["node"]["id"]) for edge in edges]

    def kinds_of(self, keys: list[str]) -> list[str]:
        return [self.kinds[key] for key in keys]


@dataclass(frozen=True)
class SearchResult:
    keys: list[str]
    kinds: list[str]
    count: int


@dataclass(frozen=True, kw_only=True)
class SearchTestCase:
    name: str
    expected: list[str]
    search: str = ""
    uuid_of: str | None = None
    """Key of the dataset object whose UUID is searched instead of `search`."""
    limit: int | None = None
    partial_match: bool = True
    case_sensitive: bool = False
    branch: str = DEFAULT_BRANCH_KEY
    """Key of the searched branch in the dataset."""
    at: str | None = None
    """Key of the dataset time to search at; the search runs at the current time when unset."""

    def __post_init__(self) -> None:
        if bool(self.search) == bool(self.uuid_of):
            raise ValueError(f"{self.name}: set exactly one of search and uuid_of")


def _uuid_fragment(uuid: str) -> str:
    """Part of a UUID after its first dash, as the leading characters encode a creation time every object shares."""
    return uuid[9:18]


async def _search(
    db: InfrahubDatabase,
    dataset: SearchDataset,
    search: str,
    branch: str = DEFAULT_BRANCH_KEY,
    at: str | None = None,
    limit: int | None = None,
    partial_match: bool = True,
    case_sensitive: bool = False,
) -> SearchResult:
    searched_branch = dataset.branches[branch]
    searched_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=searched_branch, at=dataset.times[at] if at else None)
    variables: dict[str, Any] = {"search": search, "partialMatch": partial_match, "caseSensitive": case_sensitive}
    # An explicit null limit lifts the limit, so the default is checked by leaving the variable out.
    if limit is not None:
        variables["limit"] = limit
    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_WITH_OPTIONS_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )
    assert result.errors is None
    assert result.data
    data = result.data["InfrahubSearchAnywhere"]
    return SearchResult(
        keys=dataset.keys(data["edges"]),
        kinds=[edge["node"]["kind"] for edge in data["edges"]],
        count=data["count"],
    )


async def _search_case(db: InfrahubDatabase, dataset: SearchDataset, test_case: SearchTestCase) -> SearchResult:
    return await _search(
        db=db,
        dataset=dataset,
        search=dataset.ids[test_case.uuid_of] if test_case.uuid_of else test_case.search,
        branch=test_case.branch,
        at=test_case.at,
        limit=test_case.limit,
        partial_match=test_case.partial_match,
        case_sensitive=test_case.case_sensitive,
    )


def _assert_found(result: SearchResult, dataset: SearchDataset, expected: list[str]) -> None:
    assert result.keys == expected
    assert result.count == len(expected)
    assert result.kinds == dataset.kinds_of(expected)


VOLT_RANKING = [
    "Volt",
    "Volt-01",
    "VoLt-max",
    "Volt team",
    "Volt twins (first)",
    "Volt twins (second)",
    "vOlt Oddity",
    "Voltron blue",
    "VOLT Bay North",
    "Old Volt",
    "Café Volta",
    "Ampere",
    "Voltage",
    "Ohm",
    "Watt",
]

RANKING_TEST_CASES: list[SearchTestCase] = [
    SearchTestCase(
        name="display_label_then_other_attributes_shortest_first",
        search="volt",
        limit=50,
        expected=VOLT_RANKING,
    ),
    SearchTestCase(name="ranking_ignores_the_case_of_the_search", search="VOLT", limit=50, expected=VOLT_RANKING),
    SearchTestCase(
        name="default_limit_keeps_the_ten_best",
        search="volt",
        expected=[
            "Volt",
            "Volt-01",
            "VoLt-max",
            "Volt team",
            "Volt twins (first)",
            "Volt twins (second)",
            "vOlt Oddity",
            "Voltron blue",
            "VOLT Bay North",
            "Old Volt",
        ],
    ),
    SearchTestCase(
        name="limit_counts_objects_and_groups_together",
        search="volt",
        limit=4,
        expected=["Volt", "Volt-01", "VoLt-max", "Volt team"],
    ),
    SearchTestCase(name="limit_keeps_the_best", search="volt", limit=3, expected=["Volt", "Volt-01", "VoLt-max"]),
]

SEARCH_MODE_TEST_CASES: list[SearchTestCase] = [
    SearchTestCase(
        name="case_sensitive_finds_the_lowercase_uppercase_and_title_spellings",
        search="volt",
        limit=50,
        case_sensitive=True,
        expected=[
            "Volt",
            "Volt-01",
            "Volt team",
            "Volt twins (first)",
            "Volt twins (second)",
            "Voltron blue",
            "VOLT Bay North",
            "Old Volt",
            "Café Volta",
            "Ampere",
            "Voltage",
            "Ohm",
            "Watt",
        ],
    ),
    SearchTestCase(
        name="case_sensitive_also_finds_the_spelling_as_typed",
        search="vOlt",
        limit=50,
        case_sensitive=True,
        expected=[
            "Volt",
            "Volt-01",
            "Volt team",
            "Volt twins (first)",
            "Volt twins (second)",
            "vOlt Oddity",
            "Voltron blue",
            "VOLT Bay North",
            "Old Volt",
            "Café Volta",
            "Ampere",
            "Voltage",
            "Ohm",
            "Watt",
        ],
    ),
    SearchTestCase(name="exact_match_ignores_case", search="VOLT", partial_match=False, expected=["Volt", "Ampere"]),
    SearchTestCase(
        name="exact_match_finds_a_whole_value",
        search="volt bay north",
        partial_match=False,
        expected=["VOLT Bay North"],
    ),
    SearchTestCase(
        name="exact_case_sensitive_match_finds_the_four_spellings",
        search="Volt",
        partial_match=False,
        case_sensitive=True,
        expected=["Volt", "Ampere"],
    ),
    SearchTestCase(
        name="exact_case_sensitive_match_skips_other_spellings",
        search="Volt Bay North",
        partial_match=False,
        case_sensitive=True,
        expected=[],
    ),
]

PLAIN_TEXT_TEST_CASES: list[SearchTestCase] = [
    SearchTestCase(name="double_quote", search='say "hi', expected=['Say "hi"']),
    SearchTestCase(name="apostrophe", search="it's", expected=["It's"]),
    SearchTestCase(name="backslash", search="back\\slash", expected=["back\\slash"]),
    SearchTestCase(name="percent_sign", search="100%", expected=["100% pure"]),
    SearchTestCase(name="regular_expression", search=".*", expected=["dot.star .*"]),
    SearchTestCase(name="single_character", search="q", expected=["Q"]),
    SearchTestCase(name="accented_text", search="café", expected=["Café Volta"]),
    SearchTestCase(name="no_match_returns_an_empty_list", search="nothing-to-be-found", expected=[]),
]

UUID_TEST_CASES: list[SearchTestCase] = [
    SearchTestCase(name="object", uuid_of="Volt", expected=["Volt"]),
    SearchTestCase(name="group", uuid_of="Volt team", expected=["Volt team"]),
    SearchTestCase(name="unknown_uuid", search=UNKNOWN_UUID, expected=[]),
]


class TestSearchRanking:
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> SearchDataset:
        await load_schema(db=db, schema=CAR_SCHEMA)
        dataset = SearchDataset(branches={DEFAULT_BRANCH_KEY: default_branch_scope_class})

        # Values of one rank are created longest first so the order proves the length rule, and the twins tie on purpose.
        volt = await dataset.create(db, "Volt", TestKind.PERSON, name="Volt", description="volt")
        await dataset.create(db, "VOLT Bay North", TestKind.PERSON, name="VOLT Bay North")
        await dataset.create(db, "Ohm", TestKind.PERSON, name="Ohm", description="Volt meter")
        manufacturer = await dataset.create(db, "Voltage", TestKind.MANUFACTURER, name="Voltage")
        ampere = await dataset.create(db, "Ampere", TestKind.PERSON, name="Ampere", description="volt")
        await dataset.create(
            db, "Voltron blue", TestKind.CAR, name="Voltron", color="blue", owner=ampere, manufacturer=manufacturer
        )
        await dataset.create(db, "vOlt Oddity", TestKind.PERSON, name="vOlt Oddity")
        await dataset.create(db, "Volt twins (first)", TestKind.PERSON, name="Volt twins")
        await dataset.create(db, "Volt twins (second)", TestKind.PERSON, name="Volt twins")
        await dataset.create(db, "Volt team", InfrahubKind.STANDARDGROUP, name="volt-team", label="Volt team")
        await dataset.create(db, "VoLt-max", TestKind.PERSON, name="VoLt-max")
        await dataset.create(db, "Volt-01", TestKind.PERSON, name="Volt-01")
        await dataset.create(db, "Café Volta", TestKind.PERSON, name="Café Volta")
        await dataset.create(db, "Old Volt", TestKind.PERSON, name="Old Volt")
        await dataset.create(db, "Watt", TestKind.PERSON, name="Watt", description="kilovolt")
        for name in ('Say "hi"', "It's", "back\\slash", "100% pure", "dot.star .*", "Q"):
            await dataset.create(db, name, TestKind.PERSON, name=name)
        await dataset.create(db, "uuid fragment", TestKind.PERSON, name=_uuid_fragment(volt.id))
        return dataset

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in RANKING_TEST_CASES])
    async def test_lists_the_best_matches_first(
        self, db: InfrahubDatabase, dataset: SearchDataset, test_case: SearchTestCase
    ) -> None:
        # WHEN
        result = await _search_case(db=db, dataset=dataset, test_case=test_case)

        # THEN
        _assert_found(result=result, dataset=dataset, expected=test_case.expected)

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in SEARCH_MODE_TEST_CASES])
    async def test_matches_only_what_the_search_mode_allows(
        self, db: InfrahubDatabase, dataset: SearchDataset, test_case: SearchTestCase
    ) -> None:
        # WHEN
        result = await _search_case(db=db, dataset=dataset, test_case=test_case)

        # THEN
        _assert_found(result=result, dataset=dataset, expected=test_case.expected)

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PLAIN_TEXT_TEST_CASES])
    async def test_searches_any_text_as_plain_text(
        self, db: InfrahubDatabase, dataset: SearchDataset, test_case: SearchTestCase
    ) -> None:
        # WHEN
        result = await _search_case(db=db, dataset=dataset, test_case=test_case)

        # THEN
        _assert_found(result=result, dataset=dataset, expected=test_case.expected)

    async def test_searches_a_partial_uuid_as_text(self, db: InfrahubDatabase, dataset: SearchDataset) -> None:
        # WHEN
        result = await _search(db=db, dataset=dataset, search=_uuid_fragment(dataset.ids["Volt"]))

        # THEN
        _assert_found(result=result, dataset=dataset, expected=["uuid fragment"])

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in UUID_TEST_CASES])
    async def test_finds_an_object_or_group_by_its_uuid(
        self, db: InfrahubDatabase, dataset: SearchDataset, test_case: SearchTestCase
    ) -> None:
        # WHEN
        result = await _search_case(db=db, dataset=dataset, test_case=test_case)

        # THEN
        _assert_found(result=result, dataset=dataset, expected=test_case.expected)


SEARCHED_VALUE_TEST_CASES: list[SearchTestCase] = [
    SearchTestCase(name="text", search="zephyr labs", expected=["Zephyr Labs"]),
    SearchTestCase(name="number", search="48213", expected=["Zephyr Labs"]),
    SearchTestCase(name="exact_number", search="48213", partial_match=False, expected=["Zephyr Labs"]),
    SearchTestCase(name="boolean", search="true", partial_match=False, expected=["Zephyr ticket"]),
]

UNSEARCHED_VALUE_TEST_CASES: list[SearchTestCase] = [
    SearchTestCase(name="text_area", search="nimbus", expected=[]),
    SearchTestCase(name="json", search="cirrus", expected=[]),
    SearchTestCase(name="list", search="stratus", expected=[]),
    SearchTestCase(name="list_case_sensitive", search="stratus", case_sensitive=True, expected=[]),
    SearchTestCase(name="unset_value", search="null", expected=[]),
    SearchTestCase(name="unset_value_case_sensitive", search="null", case_sensitive=True, expected=[]),
]

OBJECTS_AND_GROUPS_TEST_CASES: list[SearchTestCase] = [
    SearchTestCase(name="schema_definitions_are_not_returned", search="ticket", expected=["Ada"]),
    SearchTestCase(
        name="schema_definitions_take_no_place_within_the_limit", search="ticket", limit=1, expected=["Ada"]
    ),
    SearchTestCase(name="group_is_not_found_through_its_members", search="orion", expected=["Orion Member"]),
]


class TestSearchedValues:
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> SearchDataset:
        await load_schema(db=db, schema=CAR_SCHEMA)
        await save_schema(db=db, schema=SchemaRoot(nodes=[SEARCHED_TICKET]))
        dataset = SearchDataset(branches={DEFAULT_BRANCH_KEY: default_branch_scope_class})

        await dataset.create(
            db,
            "Zephyr ticket",
            TestKind.TICKET,
            title="Zephyr",
            ticket_id=7,
            description="nimbus cloud",
            urgent=True,
            settings={"layer": "cirrus"},
        )
        await dataset.create(db, "Zephyr Labs", TestKind.PERSON, name="Zephyr Labs", age=48213)
        await dataset.create(db, "Ada", TestKind.PERSON, name="Ada", description="Ticketing desk")
        member = await dataset.create(db, "Orion Member", TestKind.PERSON, name="Orion Member")
        await dataset.create(db, "Crew", InfrahubKind.STANDARDGROUP, name="crew", label="Crew", members=[member])
        return dataset

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in SEARCHED_VALUE_TEST_CASES])
    async def test_finds_text_numbers_and_booleans(
        self, db: InfrahubDatabase, dataset: SearchDataset, test_case: SearchTestCase
    ) -> None:
        # WHEN
        result = await _search_case(db=db, dataset=dataset, test_case=test_case)

        # THEN
        _assert_found(result=result, dataset=dataset, expected=test_case.expected)

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in UNSEARCHED_VALUE_TEST_CASES])
    async def test_never_matches_unsearched_or_empty_values(
        self, db: InfrahubDatabase, dataset: SearchDataset, test_case: SearchTestCase
    ) -> None:
        # WHEN
        result = await _search_case(db=db, dataset=dataset, test_case=test_case)

        # THEN
        _assert_found(result=result, dataset=dataset, expected=test_case.expected)

    async def test_ranks_an_object_without_a_display_label_by_its_attributes(
        self, db: InfrahubDatabase, dataset: SearchDataset
    ) -> None:
        # WHEN
        result = await _search(db=db, dataset=dataset, search="zephyr")

        # THEN
        _assert_found(result=result, dataset=dataset, expected=["Zephyr Labs", "Zephyr ticket"])

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in OBJECTS_AND_GROUPS_TEST_CASES])
    async def test_returns_only_objects_and_groups(
        self, db: InfrahubDatabase, dataset: SearchDataset, test_case: SearchTestCase
    ) -> None:
        # WHEN
        result = await _search_case(db=db, dataset=dataset, test_case=test_case)

        # THEN
        _assert_found(result=result, dataset=dataset, expected=test_case.expected)


BRANCH_A = "branch_a"
BRANCH_B = "branch_b"

BRANCH_TEST_CASES: list[SearchTestCase] = [
    SearchTestCase(name="created_on_the_branch", branch=BRANCH_A, search="branchonly", expected=["Branchonly"]),
    SearchTestCase(name="created_on_another_branch", search="branchonly", expected=[]),
    SearchTestCase(
        name="deleted_on_the_branch_leaves_its_place",
        branch=BRANCH_A,
        search="ospreya",
        limit=1,
        expected=["Ospreya Point"],
    ),
    SearchTestCase(name="deleted_on_another_branch", search="ospreya", expected=["Ospreya", "Ospreya Point"]),
    SearchTestCase(
        name="better_match_of_another_branch_takes_no_place",
        branch=BRANCH_A,
        search="kestrel",
        limit=1,
        expected=["Kestrel Bay"],
    ),
    SearchTestCase(
        name="better_match_of_the_branch_comes_first", branch=BRANCH_B, search="kestrel", limit=1, expected=["Kestrel"]
    ),
    SearchTestCase(
        name="branch_agnostic_object_on_its_branch",
        branch=BRANCH_A,
        search="lighthouse",
        expected=["Lighthouse"],
    ),
    SearchTestCase(name="branch_agnostic_object_on_another_branch", search="lighthouse", expected=["Lighthouse"]),
]

BRANCH_UUID_TEST_CASES: list[SearchTestCase] = [
    SearchTestCase(name="on_another_branch", branch=BRANCH_A, uuid_of="Kestrel", expected=[]),
    SearchTestCase(name="on_its_branch", branch=BRANCH_B, uuid_of="Kestrel", expected=["Kestrel"]),
]


class TestSearchOnBranches:
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> SearchDataset:
        await load_schema(db=db, schema=CAR_SCHEMA)
        await load_schema(db=db, schema=SchemaRoot(nodes=[AGNOSTIC_BEACON]))
        dataset = SearchDataset(branches={DEFAULT_BRANCH_KEY: default_branch_scope_class})

        for name in ("Kestrel Bay", "Ospreya", "Ospreya Point"):
            await dataset.create(db, name, TestKind.PERSON, name=name)

        branch_a = await create_branch(db=db, branch_name="search-branch-a")
        branch_b = await create_branch(db=db, branch_name="search-branch-b")
        dataset.branches.update({BRANCH_A: branch_a, BRANCH_B: branch_b})
        await dataset.create(db, "Branchonly", TestKind.PERSON, branch=branch_a, name="Branchonly")
        await dataset.delete(db, "Ospreya", branch_a)
        await dataset.create(db, "Lighthouse", BEACON_KIND, branch=branch_a, name="Lighthouse")
        await dataset.create(db, "Kestrel", TestKind.PERSON, branch=branch_b, name="Kestrel")
        return dataset

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in BRANCH_TEST_CASES])
    async def test_returns_the_objects_the_branch_shows(
        self, db: InfrahubDatabase, dataset: SearchDataset, test_case: SearchTestCase
    ) -> None:
        # WHEN
        result = await _search_case(db=db, dataset=dataset, test_case=test_case)

        # THEN
        _assert_found(result=result, dataset=dataset, expected=test_case.expected)

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in BRANCH_UUID_TEST_CASES])
    async def test_finds_by_uuid_only_objects_on_the_branch(
        self, db: InfrahubDatabase, dataset: SearchDataset, test_case: SearchTestCase
    ) -> None:
        # WHEN
        result = await _search_case(db=db, dataset=dataset, test_case=test_case)

        # THEN
        _assert_found(result=result, dataset=dataset, expected=test_case.expected)


BRANCH_X = "branch_x"
BEFORE_DELETION = "before_deletion"
BEFORE_CHANGES = "before_changes"

PAST_DATE_TEST_CASES: list[SearchTestCase] = [
    SearchTestCase(
        name="found_before_its_deletion", at=BEFORE_DELETION, search="ghost-early", expected=["Ghost-early"]
    ),
    SearchTestCase(name="deleted_before_the_date", at=BEFORE_CHANGES, search="ghost", expected=["Ghost-late"]),
    SearchTestCase(name="deleted_now", search="ghost", expected=[]),
    SearchTestCase(name="created_after_the_date", at=BEFORE_CHANGES, search="brandy", expected=[]),
    SearchTestCase(name="created_now", search="brandy", expected=["Brandy"]),
    SearchTestCase(name="old_value_at_the_date", at=BEFORE_CHANGES, search="brandon", expected=["Brandon"]),
    SearchTestCase(name="new_value_at_the_date", at=BEFORE_CHANGES, search="marlon", expected=[]),
    SearchTestCase(name="new_value_now", search="marlon", expected=["Brandon"]),
    SearchTestCase(name="old_value_now", search="brandon", expected=[]),
    SearchTestCase(
        name="ranked_by_the_display_label_at_the_date",
        at=BEFORE_CHANGES,
        search="kestrel",
        expected=["Kestrel", "Kestrel Bay"],
    ),
    SearchTestCase(name="ranked_by_the_display_label_now", search="kestrel", expected=["Kestrel Bay", "Kestrel"]),
    SearchTestCase(
        name="later_object_takes_no_place_at_the_date",
        at=BEFORE_CHANGES,
        search="brand",
        limit=1,
        expected=["Brandon"],
    ),
    SearchTestCase(
        name="deleted_best_match_at_the_date",
        at=BEFORE_CHANGES,
        search="osprey",
        expected=["Osprey", "Osprey Point"],
    ),
    SearchTestCase(
        name="deleted_best_match_leaves_its_place_now",
        search="osprey",
        limit=1,
        expected=["Osprey Point"],
    ),
    SearchTestCase(
        name="branch_object_at_the_date",
        branch=BRANCH_X,
        at=BEFORE_CHANGES,
        search="kite",
        expected=["Kite"],
    ),
    SearchTestCase(
        name="branch_old_value_at_the_date",
        branch=BRANCH_X,
        at=BEFORE_CHANGES,
        search="harrier",
        expected=["Harrier"],
    ),
    SearchTestCase(
        name="branch_new_value_at_the_date",
        branch=BRANCH_X,
        at=BEFORE_CHANGES,
        search="falcon",
        expected=[],
    ),
    SearchTestCase(name="branch_new_value_now", branch=BRANCH_X, search="falcon", expected=["Harrier"]),
    SearchTestCase(name="branch_old_value_now", branch=BRANCH_X, search="harrier", expected=[]),
]

PAST_DATE_UUID_TEST_CASES: list[SearchTestCase] = [
    SearchTestCase(name="created_after_the_date", at=BEFORE_CHANGES, uuid_of="Brandy", expected=[]),
    SearchTestCase(name="created_now", uuid_of="Brandy", expected=["Brandy"]),
    SearchTestCase(
        name="deleted_after_the_date",
        at=BEFORE_CHANGES,
        uuid_of="Ghost-late",
        expected=["Ghost-late"],
    ),
    SearchTestCase(name="deleted_now", uuid_of="Ghost-late", expected=[]),
]


class TestSearchOverTime:
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> SearchDataset:
        await load_schema(db=db, schema=CAR_SCHEMA)
        main = default_branch_scope_class
        dataset = SearchDataset(branches={DEFAULT_BRANCH_KEY: main})

        names = ("Brandon", "Kestrel", "Kestrel Bay", "Ghost-early", "Ghost-late", "Osprey", "Osprey Point", "Harrier")
        for name in names:
            await dataset.create(db, name, TestKind.PERSON, name=name)
        branch_x = await create_branch(db=db, branch_name="search-branch-x")
        dataset.branches[BRANCH_X] = branch_x
        await dataset.create(db, "Kite", TestKind.PERSON, branch=branch_x, name="Kite")

        dataset.times[BEFORE_DELETION] = Timestamp()
        await dataset.delete(db, "Ghost-early", main)
        dataset.times[BEFORE_CHANGES] = Timestamp()

        await dataset.update(db, "Brandon", main, name="Marlon")
        await dataset.update(db, "Kestrel", main, name="Old Kestrel")
        await dataset.create(db, "Brandy", TestKind.PERSON, name="Brandy")
        await dataset.delete(db, "Ghost-late", main)
        await dataset.delete(db, "Osprey", main)
        await dataset.update(db, "Harrier", branch_x, name="Falcon")
        return dataset

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PAST_DATE_TEST_CASES])
    async def test_returns_the_objects_as_they_were_at_the_date(
        self, db: InfrahubDatabase, dataset: SearchDataset, test_case: SearchTestCase
    ) -> None:
        # WHEN
        result = await _search_case(db=db, dataset=dataset, test_case=test_case)

        # THEN
        _assert_found(result=result, dataset=dataset, expected=test_case.expected)

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PAST_DATE_UUID_TEST_CASES])
    async def test_finds_by_uuid_only_objects_that_exist_at_the_date(
        self, db: InfrahubDatabase, dataset: SearchDataset, test_case: SearchTestCase
    ) -> None:
        # WHEN
        result = await _search_case(db=db, dataset=dataset, test_case=test_case)

        # THEN
        _assert_found(result=result, dataset=dataset, expected=test_case.expected)
