from typing import Any

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.core.account import ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, PermissionDecision
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import GraphqlParams, prepare_graphql_params
from infrahub.graphql.queries.search import _collapse_ipv6
from infrahub.permissions.manager import PermissionManager
from tests.helpers.graphql import graphql

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

SEARCH_QUERY_WITH_CASE_SENSITIVE = """
query ($search: String!, $caseSensitive: Boolean) {
    InfrahubSearchAnywhere(q: $search, case_sensitive: $caseSensitive) {
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


async def test_search_anywhere_by_uuid(
    db: InfrahubDatabase,
    car_accord_main: Node,
    car_camry_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    branch: Branch,
) -> None:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": car_accord_main.id},
    )

    assert result.errors is None
    assert result.data
    assert result.data["InfrahubSearchAnywhere"]["count"] == 1
    assert result.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"] == car_accord_main.id
    assert result.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["kind"] == car_accord_main.get_kind()


async def test_search_anywhere_by_string(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    branch: Branch,
) -> None:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "prius"},
    )

    assert result.errors is None
    assert result.data
    assert result.data["InfrahubSearchAnywhere"]["count"] == 1
    assert result.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"] == car_prius_main.id
    assert result.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["kind"] == car_prius_main.get_kind()

    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "j"},
    )

    assert result.errors is None
    assert result.data
    assert result.data["InfrahubSearchAnywhere"]["count"] == 2

    node_ids = []
    node_kinds = []
    for edge in result.data["InfrahubSearchAnywhere"]["edges"]:
        node_ids.append(edge["node"]["id"])
        node_kinds.append(edge["node"]["kind"])

    assert sorted(node_ids) == sorted([person_john_main.id, person_jane_main.id])
    assert sorted(node_kinds) == sorted([person_john_main.get_kind(), person_jane_main.get_kind()])


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
    """
    This only tests that ipv6 search specific behavior does not break ipv4 search.
    """
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


async def test_search_groups(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_builtin_models_schema: SchemaBranch,
    car_person_data_generic: dict[str, Node],
) -> None:
    group1 = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await group1.new(db=db, name="group1", members=[car_person_data_generic["c1"], car_person_data_generic["c2"]])
    await group1.save(db=db)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "group1"},
    )
    assert result.data
    assert result.data["InfrahubSearchAnywhere"]["count"] == 1

    assert result.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"] == group1.id


async def test_search_anywhere_by_string_no_results(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    register_builtin_models_schema: None,
) -> None:
    """Validate that the GraphQL an empty result is returned as an empty array and not a `null` value"""
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "nothing-to-be-found"},
    )

    assert result.errors is None
    assert result.data
    assert result.data["InfrahubSearchAnywhere"]["count"] == 0
    assert result.data["InfrahubSearchAnywhere"]["edges"] == []


async def test_search_anywhere_case_insensitive_default(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jane_main: Node,
    person_luffy_main: Node,
    branch: Branch,
) -> None:
    """Default search (case_sensitive=False) should find results regardless of case."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    # Search with lowercase "john" should find "John" (case-insensitive by default)
    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_CASE_SENSITIVE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "john", "caseSensitive": False},
    )

    assert result.errors is None
    assert result.data
    assert result.data["InfrahubSearchAnywhere"]["count"] == 1
    assert result.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"] == person_john_main.id

    # Search with lowercase "luffy" should find "lUffy" (case-insensitive by default)
    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_CASE_SENSITIVE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "luffy", "caseSensitive": False},
    )

    assert result.errors is None
    assert result.data
    assert result.data["InfrahubSearchAnywhere"]["count"] == 1
    assert result.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"] == person_luffy_main.id


async def test_search_anywhere_case_sensitive_enabled(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jane_main: Node,
    person_luffy_main: Node,
    branch: Branch,
) -> None:
    """Test search with case_sensitive=True uses the optimized query with case variations."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    # Search with lowercase "john" when case_sensitive=True still finds "John"
    # because the query uses case variations (lowercase, UPPERCASE, Title Case)
    result_lowercase = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_CASE_SENSITIVE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "john", "caseSensitive": True},
    )

    assert result_lowercase.errors is None
    assert result_lowercase.data
    assert result_lowercase.data["InfrahubSearchAnywhere"]["count"] == 1
    assert result_lowercase.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"] == person_john_main.id

    # Search with lowercase "luffy" when case_sensitive=True should NOT find "lUffy"
    # because "lUffy" doesn't match any standard case variation (luffy, LUFFY, Luffy)
    result_luffy = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_CASE_SENSITIVE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "luffy", "caseSensitive": True},
    )

    assert result_luffy.errors is None
    assert result_luffy.data
    assert result_luffy.data["InfrahubSearchAnywhere"]["count"] == 0

    # Search with exact case "lUffy" when case_sensitive=True should find "lUffy"
    result_exact = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_CASE_SENSITIVE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "lUffy", "caseSensitive": True},
    )

    assert result_exact.errors is None
    assert result_exact.data
    assert result_exact.data["InfrahubSearchAnywhere"]["count"] == 1
    assert result_exact.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"] == person_luffy_main.id

    # Search with exact case "John" when case_sensitive=True should also find "John"
    result_exact = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_CASE_SENSITIVE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "John", "caseSensitive": True},
    )

    assert result_exact.errors is None
    assert result_exact.data
    assert result_exact.data["InfrahubSearchAnywhere"]["count"] == 1
    assert result_exact.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"] == person_john_main.id


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


SEARCH_QUERY_WITH_PAGINATION = """
query ($search: String!, $limit: Int, $offset: Int) {
    InfrahubSearchAnywhere(q: $search, limit: $limit, offset: $offset) {
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


async def test_search_anywhere_offset_skips_results(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    branch: Branch,
) -> None:
    """Verify that offset skips the first N results."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    # Search for "j" which matches John and Jane (2 results)
    result_no_offset = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_PAGINATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "j", "limit": 10, "offset": 0},
    )

    assert result_no_offset.errors is None
    assert result_no_offset.data
    assert result_no_offset.data["InfrahubSearchAnywhere"]["count"] == 2
    assert len(result_no_offset.data["InfrahubSearchAnywhere"]["edges"]) == 2

    # With offset=1, should skip first result and return only one
    result_with_offset = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_PAGINATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "j", "limit": 10, "offset": 1},
    )

    assert result_with_offset.errors is None
    assert result_with_offset.data
    # Count reflects results fetched (capped by db_limit = offset + limit)
    assert result_with_offset.data["InfrahubSearchAnywhere"]["count"] == 2
    assert len(result_with_offset.data["InfrahubSearchAnywhere"]["edges"]) == 1


async def test_search_anywhere_count_reflects_true_total(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    branch: Branch,
) -> None:
    """Verify that count reflects the true total matching results, regardless of limit."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    # Search for "j" which matches John and Jane (2 results), with limit=2
    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_PAGINATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "j", "limit": 2, "offset": 0},
    )

    assert result.errors is None
    assert result.data
    assert result.data["InfrahubSearchAnywhere"]["count"] == 2
    assert len(result.data["InfrahubSearchAnywhere"]["edges"]) == 2

    # With limit=1, count should still be 2 (true total), but only 1 edge returned
    result_limited = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_PAGINATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "j", "limit": 1, "offset": 0},
    )

    assert result_limited.errors is None
    assert result_limited.data
    # Count reflects true total, not the page size
    assert result_limited.data["InfrahubSearchAnywhere"]["count"] == 2
    assert len(result_limited.data["InfrahubSearchAnywhere"]["edges"]) == 1


async def test_search_anywhere_offset_zero_behaves_as_default(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    branch: Branch,
) -> None:
    """Verify that offset=0 returns the same results as no offset parameter."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    result_default = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "prius"},
    )

    result_explicit_zero = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_PAGINATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "prius", "limit": 10, "offset": 0},
    )

    assert result_default.errors is None
    assert result_explicit_zero.errors is None
    assert result_default.data
    assert result_explicit_zero.data
    assert (
        result_default.data["InfrahubSearchAnywhere"]["count"]
        == result_explicit_zero.data["InfrahubSearchAnywhere"]["count"]
    )
    assert (
        result_default.data["InfrahubSearchAnywhere"]["edges"]
        == result_explicit_zero.data["InfrahubSearchAnywhere"]["edges"]
    )


async def test_search_anywhere_pagination_consistency(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    branch: Branch,
) -> None:
    """Verify that paginating through results yields all results without duplicates and with stable count."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    # Search for "j" which matches John and Jane (2 results)
    # Page 1: limit=1, offset=0
    page1 = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_PAGINATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "j", "limit": 1, "offset": 0},
    )

    # Page 2: limit=1, offset=1
    page2 = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_PAGINATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "j", "limit": 1, "offset": 1},
    )

    assert page1.errors is None
    assert page2.errors is None
    assert page1.data
    assert page2.data

    # Count should be stable across pages (always the true total)
    assert page1.data["InfrahubSearchAnywhere"]["count"] == 2
    assert page2.data["InfrahubSearchAnywhere"]["count"] == 2

    # Each page should have exactly 1 result
    assert len(page1.data["InfrahubSearchAnywhere"]["edges"]) == 1
    assert len(page2.data["InfrahubSearchAnywhere"]["edges"]) == 1

    # Combined results should cover all matches without duplicates
    page1_id = page1.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"]
    page2_id = page2.data["InfrahubSearchAnywhere"]["edges"][0]["node"]["id"]
    assert page1_id != page2_id
    assert sorted([page1_id, page2_id]) == sorted([person_john_main.id, person_jane_main.id])


def _create_restricted_permission_manager(
    object_permissions: list[ObjectPermission],
) -> PermissionManager:
    """Create a PermissionManager with specific object permissions (non-admin)."""
    session = AccountSession(authenticated=True, auth_type=AuthType.API, account_id="test-restricted-user")
    manager = PermissionManager(account_session=session)
    manager.permissions = {
        "global_permissions": [],
        "object_permissions": object_permissions,
    }
    return manager


async def test_search_permission_restricted_user_sees_only_permitted_kinds(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    branch: Branch,
) -> None:
    """Restricted user should only see search results for kinds they have view permission on."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    # Set up permissions: allow TestPerson view, deny everything else
    gql_params.context.permissions = _create_restricted_permission_manager(
        object_permissions=[
            ObjectPermission(
                namespace="Test",
                name="Person",
                action="view",
                decision=PermissionDecision.ALLOW_ALL,
            ),
            ObjectPermission(
                namespace="*",
                name="*",
                action="view",
                decision=PermissionDecision.DENY,
            ),
        ],
    )

    # Search for "j" — matches John and Jane (TestPerson) but not cars
    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "j"},
    )

    assert result.errors is None
    assert result.data
    # Only TestPerson results should be visible — cars are filtered out
    assert result.data["InfrahubSearchAnywhere"]["count"] == 2
    for edge in result.data["InfrahubSearchAnywhere"]["edges"]:
        assert edge["node"]["kind"] == person_john_main.get_kind()

    node_ids = [edge["node"]["id"] for edge in result.data["InfrahubSearchAnywhere"]["edges"]]
    assert sorted(node_ids) == sorted([person_john_main.id, person_jane_main.id])

    # Search for "prius" — matches a car but user can't view TestCar
    result_car = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "prius"},
    )

    assert result_car.errors is None
    assert result_car.data
    assert result_car.data["InfrahubSearchAnywhere"]["count"] == 0
    assert result_car.data["InfrahubSearchAnywhere"]["edges"] == []


async def test_search_permission_admin_sees_all_results(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    branch: Branch,
) -> None:
    """Admin user (permissions=None) should see all results with no filtering overhead."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    # Default: permissions is None (admin/no-auth context) — no filtering applied
    assert gql_params.context.permissions is None

    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "j"},
    )

    assert result.errors is None
    assert result.data
    # Both John and Jane should be found (no filtering)
    assert result.data["InfrahubSearchAnywhere"]["count"] == 2
    node_ids = [edge["node"]["id"] for edge in result.data["InfrahubSearchAnywhere"]["edges"]]
    assert sorted(node_ids) == sorted([person_john_main.id, person_jane_main.id])


async def test_search_permission_no_permissions_returns_empty(
    db: InfrahubDatabase,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    branch: Branch,
) -> None:
    """User with no view permissions for any type should get empty results."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    # Set up permissions: deny all kinds
    gql_params.context.permissions = _create_restricted_permission_manager(
        object_permissions=[
            ObjectPermission(
                namespace="*",
                name="*",
                action="view",
                decision=PermissionDecision.DENY,
            ),
        ],
    )

    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "j"},
    )

    assert result.errors is None
    assert result.data
    # Short-circuit: empty allowed_kinds list → count=0, no edges
    assert result.data["InfrahubSearchAnywhere"]["count"] == 0
    assert result.data["InfrahubSearchAnywhere"]["edges"] == []
