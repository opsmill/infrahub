import pytest
from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.queries.search import _collapse_ipv6

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


async def test_search_anywhere_by_uuid(
    db: InfrahubDatabase,
    car_accord_main: Node,
    car_camry_main: Node,
    car_volt_main: Node,
    car_prius_main: Node,
    car_yaris_main: Node,
    branch: Branch,
):
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)

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
):
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)

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
):
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)

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
    ip_dataset_01,
    branch: Branch,
):
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)

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
):
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)

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
):
    """
    This only tests that ipv6 search specific behavior does not break ipv4 search.
    """

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)

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
def test_collapse_ipv6_address_or_network(query, expected):
    assert _collapse_ipv6(query) == expected


@pytest.mark.parametrize(
    "query",
    ["invalid", "invalid:case", "2001:invalid", "2001:0db81:0000", "10.0.0.0", "2001:db8:1"],
)
def test_collapse_ipv6_address_or_network_invalid_cases(query):
    with pytest.raises(ValueError):
        _collapse_ipv6(query)
