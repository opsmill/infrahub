import ipaddress

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.queries.search import _collapse_ipv6, _try_parse_ip_or_prefix
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

SEARCH_QUERY_WITH_PREFIX_LOOKUP = """
query ($search: String!) {
    InfrahubSearchAnywhere(q: $search) {
        count
        is_prefix_lookup
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
    ip_dataset_01,
    branch: Branch,
) -> None:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    res_collapsed = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_PREFIX_LOOKUP,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "2001:db8::"},
    )

    res_extended = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_PREFIX_LOOKUP,
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

    # Both formats trigger the prefix lookup path
    assert res_collapsed.data["InfrahubSearchAnywhere"]["is_prefix_lookup"] is True
    assert res_extended.data["InfrahubSearchAnywhere"]["is_prefix_lookup"] is True


async def test_search_ipv6_network_extended_format(
    db: InfrahubDatabase,
    ip_dataset_01,
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
    ip_dataset_01,
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
    ip_dataset_01,
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
def test_collapse_ipv6_address_or_network(query, expected) -> None:
    assert _collapse_ipv6(query) == expected


@pytest.mark.parametrize(
    "query",
    ["invalid", "invalid:case", "2001:invalid", "2001:0db81:0000", "10.0.0.0", "2001:db8:1"],
)
def test_collapse_ipv6_address_or_network_invalid_cases(query) -> None:
    with pytest.raises(ValueError):
        _collapse_ipv6(query)


@pytest.mark.parametrize(
    "input_str,expected_type",
    [
        ("10.1.2.45", ipaddress.IPv4Address),
        ("0.0.0.0", ipaddress.IPv4Address),  # noqa: S104
        ("2001:db8::1", ipaddress.IPv6Address),
        ("2001:0db8:0000::1", ipaddress.IPv6Address),
        ("::1", ipaddress.IPv6Address),
        ("10.0.0.0/8", ipaddress.IPv4Network),
        ("10.1.2.0/24", ipaddress.IPv4Network),
        ("2001:db8::/32", ipaddress.IPv6Network),
        ("10.1.2", None),
        ("router-core-01", None),
        ("", None),
        ("10.0.0.0/33", None),
    ],
)
def test_try_parse_ip_or_prefix(input_str, expected_type) -> None:
    result = _try_parse_ip_or_prefix(input_str)
    if expected_type is None:
        assert result is None
    else:
        assert isinstance(result, expected_type)


async def test_search_prefix_lookup_ipv4_address(
    db: InfrahubDatabase,
    ip_dataset_01,
    branch: Branch,
) -> None:
    """Searching for a valid IPv4 address returns parent prefixes via prefix lookup."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_PREFIX_LOOKUP,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "10.10.1.1"},
    )

    assert result.errors is None
    assert result.data
    data = result.data["InfrahubSearchAnywhere"]
    assert data["is_prefix_lookup"] is True

    # 10.10.1.1 is contained in:
    #   NS1: net143 (10.10.1.0/27), net142 (10.10.1.0/24), net140 (10.10.0.0/16), net146 (10.0.0.0/8)
    #   NS2: net240 (10.10.0.0/15)
    # Ordered by prefix length DESC
    assert data["count"] == 5
    result_ids = [edge["node"]["id"] for edge in data["edges"]]
    assert ip_dataset_01["net143"].id in result_ids
    assert ip_dataset_01["net142"].id in result_ids
    assert ip_dataset_01["net140"].id in result_ids
    assert ip_dataset_01["net240"].id in result_ids
    assert ip_dataset_01["net146"].id in result_ids

    # All results should be IP prefixes
    for edge in data["edges"]:
        assert edge["node"]["kind"] == InfrahubKind.IPPREFIX

    # Results ordered by prefix length descending
    assert result_ids[0] == ip_dataset_01["net143"].id  # /27
    assert result_ids[-1] == ip_dataset_01["net146"].id  # /8


async def test_search_prefix_lookup_ipv4_prefix(
    db: InfrahubDatabase,
    ip_dataset_01,
    branch: Branch,
) -> None:
    """Searching for a valid IPv4 CIDR prefix returns the exact match and parent prefixes."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_PREFIX_LOOKUP,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "10.10.1.0/24"},
    )

    assert result.errors is None
    assert result.data
    data = result.data["InfrahubSearchAnywhere"]
    assert data["is_prefix_lookup"] is True

    # 10.10.1.0/24 matches (exact or parent):
    #   NS1: net142 (10.10.1.0/24 exact), net140 (10.10.0.0/16), net146 (10.0.0.0/8)
    #   NS2: net240 (10.10.0.0/15)
    # Does NOT include net143 (10.10.1.0/27) since it's a child
    assert data["count"] == 4
    result_ids = [edge["node"]["id"] for edge in data["edges"]]
    assert ip_dataset_01["net142"].id in result_ids
    assert ip_dataset_01["net140"].id in result_ids
    assert ip_dataset_01["net240"].id in result_ids
    assert ip_dataset_01["net146"].id in result_ids
    assert ip_dataset_01["net143"].id not in result_ids


@pytest.mark.parametrize("search_term", ["10.1.2", "ns1"])
async def test_search_prefix_lookup_text_fallback(
    db: InfrahubDatabase,
    ip_dataset_01,
    branch: Branch,
    search_term: str,
) -> None:
    """Non-IP text and partial IPs fall through to text search (is_prefix_lookup=None)."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_PREFIX_LOOKUP,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": search_term},
    )

    assert result.errors is None
    assert result.data
    assert result.data["InfrahubSearchAnywhere"]["is_prefix_lookup"] is None


async def test_search_prefix_lookup_no_matching_prefixes(
    db: InfrahubDatabase,
    ip_dataset_01,
    branch: Branch,
) -> None:
    """A valid IP with no matching prefixes in the DB returns is_prefix_lookup=true with count=0."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    result = await graphql(
        schema=gql_params.schema,
        source=SEARCH_QUERY_WITH_PREFIX_LOOKUP,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"search": "172.16.0.1"},
    )

    assert result.errors is None
    assert result.data
    data = result.data["InfrahubSearchAnywhere"]
    assert data["is_prefix_lookup"] is True
    assert data["count"] == 0
    assert data["edges"] == []


async def test_search_groups(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema,
    register_builtin_models_schema,
    car_person_data_generic,
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
