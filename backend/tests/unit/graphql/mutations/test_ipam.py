import ipaddress

from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.core.schema_manager import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params

CREATE_IPPREFIX = """
mutation CreatePrefix($prefix: String!) {
    IpamIPPrefixCreate(
        data: {
            prefix: {
                value: $prefix
            }
        }
    ) {
        ok
        object {
            id
        }
    }
}
"""

DELETE_IPPREFIX = """
mutation DeletePrefix($id: String!) {
    IpamIPPrefixDelete(
        data: {
            id: $id
        }
    ) {
        ok
    }
}
"""

GET_IPPREFIX = """
query GetPrefixWithParent($prefix: String!) {
    IpamIPPrefix(prefix__value: $prefix) {
        edges {
            node {
                id
                prefix {
                    value
                }
                parent {
                    node {
                        id
                        prefix {
                            value
                        }
                    }
                }
            }
        }
    }
}
"""


async def test_ipprefix_create(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    """Make sure prefix can be created and parent/children relationships are set."""
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    supernet = ipaddress.ip_network("2001:db8::/32")
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"prefix": str(supernet)},
    )

    assert not result.errors
    assert result.data["IpamIPPrefixCreate"]["ok"]

    result = await graphql(
        schema=gql_params.schema,
        source=GET_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"prefix": str(supernet)},
    )

    assert not result.errors
    assert len(result.data["IpamIPPrefix"]["edges"]) == 1
    assert not result.data["IpamIPPrefix"]["edges"][0]["node"]["parent"]["node"]
    assert result.data["IpamIPPrefix"]["edges"][0]["node"]["prefix"]["value"] == str(supernet)

    networks = list(supernet.subnets(new_prefix=36))
    for n in networks:
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_IPPREFIX,
            context_value=gql_params.context,
            variable_values={"prefix": str(n)},
        )

        assert not result.errors
        assert result.data["IpamIPPrefixCreate"]["ok"]

    result = await graphql(
        schema=gql_params.schema,
        source=GET_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"prefix": str(networks[0])},
    )

    assert not result.errors
    assert len(result.data["IpamIPPrefix"]["edges"]) == 1
    assert result.data["IpamIPPrefix"]["edges"][0]["node"]["parent"]["node"]["prefix"]["value"] == str(supernet)


async def test_ipprefix_create_reverse(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    """Make sure parent/children relationship are set when creating a parent after a child."""
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    subnet = ipaddress.ip_network("2001:db8::/48")
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"prefix": str(subnet)},
    )

    assert not result.errors
    assert result.data["IpamIPPrefixCreate"]["ok"]

    supernet = ipaddress.ip_network("2001:db8::/32")
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"prefix": str(supernet)},
    )

    assert not result.errors
    assert result.data["IpamIPPrefixCreate"]["ok"]

    result = await graphql(
        schema=gql_params.schema,
        source=GET_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"prefix": str(subnet)},
    )

    assert not result.errors
    assert len(result.data["IpamIPPrefix"]["edges"]) == 1
    assert result.data["IpamIPPrefix"]["edges"][0]["node"]["parent"]["node"]["prefix"]["value"] == str(supernet)


async def test_ipprefix_delete(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    """Make sure parent/children relationship are set when creating a parent after a child."""
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    networks = [
        ipaddress.ip_network("2001:db8::/32"),
        ipaddress.ip_network("2001:db8::/48"),
        ipaddress.ip_network("2001:db8::/56"),
        ipaddress.ip_network("2001:db8::/64"),
    ]
    network_nodes = []
    for n in networks:
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_IPPREFIX,
            context_value=gql_params.context,
            variable_values={"prefix": str(n)},
        )

        assert not result.errors
        assert result.data["IpamIPPrefixCreate"]["ok"]
        network_nodes.append(result.data["IpamIPPrefixCreate"]["object"]["id"])

    result = await graphql(
        schema=gql_params.schema,
        source=DELETE_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"id": network_nodes[0]},
    )

    assert not result.errors
    assert result.data["IpamIPPrefixDelete"]["ok"]

    result = await graphql(
        schema=gql_params.schema,
        source=GET_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"prefix": str(networks[1])},
    )

    # Removing the parent prefix means this prefix' parent should now be null
    assert not result.errors
    assert len(result.data["IpamIPPrefix"]["edges"]) == 1
    assert not result.data["IpamIPPrefix"]["edges"][0]["node"]["parent"]["node"]

    result = await graphql(
        schema=gql_params.schema,
        source=DELETE_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"id": network_nodes[2]},
    )

    assert not result.errors
    assert result.data["IpamIPPrefixDelete"]["ok"]

    result = await graphql(
        schema=gql_params.schema,
        source=GET_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"prefix": str(networks[3])},
    )

    # Removing a node in the mddle should relocate children prefixes to a new parent prefix
    assert not result.errors
    assert len(result.data["IpamIPPrefix"]["edges"]) == 1
    assert result.data["IpamIPPrefix"]["edges"][0]["node"]["parent"]["node"]["id"] == network_nodes[1]
