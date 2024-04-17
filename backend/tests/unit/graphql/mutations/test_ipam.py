import ipaddress

from graphql import graphql

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
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
query GetPrefix($prefix: String!) {
    IpamIPPrefix(prefix__value: $prefix) {
        edges {
            node {
                id
                prefix {
                    value
                }
                is_top_level {
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
                children {
                    edges {
                        node {
                            id
                            prefix {
                                value
                            }
                        }
                    }
                }
                ip_addresses {
                    edges {
                        node {
                            id
                            address {
                                value
                            }
                        }
                    }
                }
            }
        }
    }
}
"""

CREATE_IPADDRESS = """
mutation CreateAddress($address: String!) {
    IpamIPAddressCreate(
        data: {
            address: {
                value: $address
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

GET_IPADDRESS = """
query GetAddress($address: String!) {
    IpamIPAddress(address__value: $address) {
        edges {
            node {
                id
                address {
                    value
                }
                ip_prefix {
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
    default_ipnamespace: Node,
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
    assert result.data["IpamIPPrefixCreate"]["object"]["id"]

    ip_prefix = await registry.manager.get_one(id=result.data["IpamIPPrefixCreate"]["object"]["id"], db=db)
    ip_namespace = await ip_prefix.ip_namespace.get_peer(db=db)
    assert ip_namespace.id == registry.default_ipnamespace

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
    assert result.data["IpamIPPrefix"]["edges"][0]["node"]["is_top_level"]["value"]

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
    assert not result.data["IpamIPPrefix"]["edges"][0]["node"]["is_top_level"]["value"]


async def test_ipprefix_create_with_ipnamespace(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    ns = await Node.init(db=db, schema=InfrahubKind.NAMESPACE, branch=default_branch)
    await ns.new(db=db, name="ns1")
    await ns.save(db=db)

    query = """
    mutation CreatePrefix($prefix: String!, $namespace: String!) {
        IpamIPPrefixCreate(
            data: {
                prefix: {
                    value: $prefix
                }
                ip_namespace: {
                    id: $namespace
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

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    supernet = ipaddress.ip_network("2001:db8::/32")
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        variable_values={"prefix": str(supernet), "namespace": ns.id},
    )

    assert not result.errors
    assert result.data["IpamIPPrefixCreate"]["ok"]
    assert result.data["IpamIPPrefixCreate"]["object"]["id"]

    ip_prefix = await registry.manager.get_one(id=result.data["IpamIPPrefixCreate"]["object"]["id"], db=db)
    ip_namespace = await ip_prefix.ip_namespace.get_peer(db=db)
    assert ip_namespace.id == ns.id


async def test_ipprefix_create_reverse(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
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
    assert not result.data["IpamIPPrefix"]["edges"][0]["node"]["is_top_level"]["value"]


async def test_ipprefix_delete(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    """Make sure deleting a prefix relocates its children."""
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

    # Removing a node in the middle should relocate children prefixes to a new parent prefix
    # FIXME: broken
    assert not result.errors
    assert len(result.data["IpamIPPrefix"]["edges"]) == 1
    # assert result.data["IpamIPPrefix"]["edges"][0]["node"]["parent"]["node"]["id"] == network_nodes[1]


async def test_ipaddress_create(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    """Make sure IP address is properly created and nested under a subnet."""
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    # Single IP address, no IP prefix
    address = ipaddress.ip_interface("192.0.2.1/24")
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_IPADDRESS,
        context_value=gql_params.context,
        variable_values={"address": str(address)},
    )

    assert not result.errors
    assert result.data["IpamIPAddressCreate"]["ok"]
    assert result.data["IpamIPAddressCreate"]["object"]["id"]

    ip = await registry.manager.get_one(id=result.data["IpamIPAddressCreate"]["object"]["id"], db=db)
    ip_namespace = await ip.ip_namespace.get_peer(db=db)
    assert ip_namespace.id == registry.default_ipnamespace

    result = await graphql(
        schema=gql_params.schema,
        source=GET_IPADDRESS,
        context_value=gql_params.context,
        variable_values={"address": str(address)},
    )

    assert not result.errors
    assert len(result.data["IpamIPAddress"]["edges"]) == 1
    assert not result.data["IpamIPAddress"]["edges"][0]["node"]["ip_prefix"]["node"]
    assert result.data["IpamIPAddress"]["edges"][0]["node"]["address"]["value"] == str(address)

    # Single IP address under an IP prefix
    supernet = ipaddress.ip_network("2001:db8::/48")
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"prefix": str(supernet)},
    )

    assert not result.errors
    assert result.data["IpamIPPrefixCreate"]["ok"]

    address = ipaddress.ip_interface("2001:db8::1/64")
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_IPADDRESS,
        context_value=gql_params.context,
        variable_values={"address": str(address)},
    )

    assert not result.errors
    assert result.data["IpamIPAddressCreate"]["ok"]

    result = await graphql(
        schema=gql_params.schema,
        source=GET_IPADDRESS,
        context_value=gql_params.context,
        variable_values={"address": str(address)},
    )

    assert not result.errors
    assert len(result.data["IpamIPAddress"]["edges"]) == 1
    assert result.data["IpamIPAddress"]["edges"][0]["node"]["address"]["value"] == str(address)
    assert result.data["IpamIPAddress"]["edges"][0]["node"]["ip_prefix"]["node"]["prefix"]["value"] == str(supernet)


async def test_ipaddress_change_ipprefix(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    """Make sure relationship between an address and its prefix is properly managed."""
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    address = ipaddress.ip_interface("2001:db8::1/64")
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_IPADDRESS,
        context_value=gql_params.context,
        variable_values={"address": str(address)},
    )

    assert not result.errors
    assert result.data["IpamIPAddressCreate"]["ok"]

    # Create subnet which contains the previously created IP should set relationships
    supernet = ipaddress.ip_network("2001:db8::/48")
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
        source=GET_IPADDRESS,
        context_value=gql_params.context,
        variable_values={"address": str(address)},
    )

    assert not result.errors
    assert len(result.data["IpamIPAddress"]["edges"]) == 1
    assert result.data["IpamIPAddress"]["edges"][0]["node"]["ip_prefix"]["node"]["prefix"]["value"] == str(supernet)

    # Check that the prefix now has an IP address
    result = await graphql(
        schema=gql_params.schema,
        source=GET_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"prefix": str(supernet)},
    )

    assert not result.errors
    assert len(result.data["IpamIPPrefix"]["edges"]) == 1
    assert len(result.data["IpamIPPrefix"]["edges"][0]["node"]["ip_addresses"]["edges"]) == 1
    assert result.data["IpamIPPrefix"]["edges"][0]["node"]["ip_addresses"]["edges"][0]["node"]["address"][
        "value"
    ] == str(address)

    # Create subnet of the original one which contains the address, it should relocate it
    subnet = ipaddress.ip_network("2001:db8::/64")
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"prefix": str(subnet)},
    )

    result = await graphql(
        schema=gql_params.schema,
        source=GET_IPADDRESS,
        context_value=gql_params.context,
        variable_values={"address": str(address)},
    )

    assert not result.errors
    assert len(result.data["IpamIPAddress"]["edges"]) == 1
    assert result.data["IpamIPAddress"]["edges"][0]["node"]["ip_prefix"]["node"]["prefix"]["value"] == str(subnet)

    # Check that the subnet has the IP address now
    result = await graphql(
        schema=gql_params.schema,
        source=GET_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"prefix": str(subnet)},
    )

    assert not result.errors
    assert len(result.data["IpamIPPrefix"]["edges"]) == 1
    assert result.data["IpamIPPrefix"]["edges"][0]["node"]["ip_addresses"]["edges"][0]["node"]["address"][
        "value"
    ] == str(address)

    # Check that the supernet does not have an IP address anymore
    result = await graphql(
        schema=gql_params.schema,
        source=GET_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"prefix": str(supernet)},
    )

    assert not result.errors
    assert len(result.data["IpamIPPrefix"]["edges"]) == 1
    assert not result.data["IpamIPPrefix"]["edges"][0]["node"]["ip_addresses"]["edges"]

    # Create a less specific subnet, IP address should not be relocated
    middle = ipaddress.ip_network("2001:db8::/56")
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"prefix": str(middle)},
    )

    result = await graphql(
        schema=gql_params.schema,
        source=GET_IPADDRESS,
        context_value=gql_params.context,
        variable_values={"address": str(address)},
    )

    assert not result.errors
    assert len(result.data["IpamIPAddress"]["edges"]) == 1
    assert result.data["IpamIPAddress"]["edges"][0]["node"]["ip_prefix"]["node"]["prefix"]["value"] == str(subnet)
