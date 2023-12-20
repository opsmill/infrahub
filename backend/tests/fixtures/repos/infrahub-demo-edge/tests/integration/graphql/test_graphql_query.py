import pytest
from infrahub_ctl.utils import find_graphql_query
from infrahub_sdk import InfrahubClientSync


@pytest.mark.parametrize(
    "query_name,variables",
    [
        ("device_startup_info", {"device": "ord1-edge1"}),
        ("oc_interfaces", {"device": "ord1-edge1"}),
        ("oc_bgp_neighbors", {"device": "ord1-edge1"}),
        ("topology_info", {}),
        ("check_backbone_link_redundancy", {}),
    ],
)
def test_graphql_queries(root_directory, client_sync: InfrahubClientSync, query_name: str, variables: dict):
    query_str = find_graphql_query(name=query_name, directory=root_directory)
    response = client_sync.execute_graphql(query=query_str, variables=variables, raise_for_error=False)

    assert "errors" not in response
