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

UPDATE_IPPREFIX = """
mutation UpdatePrefix($id: String!, $prefix: String!, $description: String!) {
    IpamIPPrefixUpdate(
        data: {
            id: $id
            prefix: {
                value: $prefix
            }
            description: {
                value: $description
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

UPSERT_IPPREFIX = """
mutation UpsertPrefix($id: String!, $prefix: String!, $description: String!) {
    IpamIPPrefixUpsert(
        data: {
            id: $id
            prefix: {
                value: $prefix
            }
            description: {
                value: $description
            }
        }
    ) {
        ok
        object {
            id
            description {
                value
            }
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

UPDATE_IPADDRESS = """
mutation UpdateAddress($id: String!, $address: String!, $description: String!) {
    IpamIPAddressUpdate(
        data: {
            id: $id
            address: {
                value: $address
            }
            description: {
                value: $description
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

UPSERT_IPADDRESS = """
mutation UpsertAddress($id: String!, $address: String!, $description: String!) {
    IpamIPAddressUpsert(
        data: {
            id: $id
            address: {
                value: $address
            }
            description: {
                value: $description
            }
        }
    ) {
        ok
        object {
            id
            description {
                value
            }
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

DELETE_IPNAMESPACE = """
mutation NamespaceDelete($namespace_id: String!) {
    IpamNamespaceDelete(data: {id: $namespace_id}) {
        ok
    }
}
"""


async def test_protected_default_ipnamespace(db: InfrahubDatabase, default_branch: Branch, default_ipnamespace: Node):
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=DELETE_IPNAMESPACE,
        context_value=gql_params.context,
        variable_values={"namespace_id": registry.default_ipnamespace},
    )

    assert result.errors
    assert result.errors[0].message == "Cannot delete default IPAM namespace"


async def test_delete_regular_ipnamespace(db: InfrahubDatabase, default_branch: Branch, default_ipnamespace: Node):
    ns1 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns1.new(db=db, name="ns1")
    await ns1.save(db=db)

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=DELETE_IPNAMESPACE,
        context_value=gql_params.context,
        variable_values={"namespace_id": ns1.id},
    )

    assert not result.errors
    assert result.data["IpamNamespaceDelete"]["ok"]


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


async def test_ipprefix_update(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    """Make sure a prefix can be updated."""
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

    subnet_id = result.data["IpamIPPrefixCreate"]["object"]["id"]
    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"id": subnet_id, "prefix": str(subnet), "description": "RFC 3849"},
    )

    assert not result.errors
    assert result.data["IpamIPPrefixUpdate"]["ok"]


async def test_ipprefix_upsert(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    """Make sure a prefix can be upserted."""
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    subnet = ipaddress.ip_network("2001:db8::/48")
    result = await graphql(
        schema=gql_params.schema,
        source=UPSERT_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"id": "", "prefix": str(subnet), "description": ""},
    )

    assert not result.errors
    assert result.data["IpamIPPrefixUpsert"]["ok"]
    assert not result.data["IpamIPPrefixUpsert"]["object"]["description"]["value"]

    subnet_id = result.data["IpamIPPrefixUpsert"]["object"]["id"]
    result = await graphql(
        schema=gql_params.schema,
        source=UPSERT_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"id": subnet_id, "prefix": str(subnet), "description": "RFC 3849"},
    )

    assert not result.errors
    assert result.data["IpamIPPrefixUpsert"]["ok"]
    assert result.data["IpamIPPrefixUpsert"]["object"]["description"]["value"] == "RFC 3849"


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
    assert result.data["IpamIPPrefix"]["edges"][0]["node"]["is_top_level"]["value"] is True

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
    assert not result.errors
    assert len(result.data["IpamIPPrefix"]["edges"]) == 1
    assert result.data["IpamIPPrefix"]["edges"][0]["node"]["parent"]["node"]["id"] == network_nodes[1]


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


async def test_ipaddress_update(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    """Make sure an IP address can be updated."""
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    address = ipaddress.ip_interface("192.0.2.1/24")
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_IPADDRESS,
        context_value=gql_params.context,
        variable_values={"address": str(address)},
    )

    assert not result.errors
    assert result.data["IpamIPAddressCreate"]["ok"]

    address_id = result.data["IpamIPAddressCreate"]["object"]["id"]
    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_IPADDRESS,
        context_value=gql_params.context,
        variable_values={"id": address_id, "address": str(address), "description": "RFC 5735"},
    )

    assert not result.errors
    assert result.data["IpamIPAddressUpdate"]["ok"]


async def test_ipaddress_upsert(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    """Make sure an IP address can be upsert."""
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    address = ipaddress.ip_interface("192.0.2.1/24")
    result = await graphql(
        schema=gql_params.schema,
        source=UPSERT_IPADDRESS,
        context_value=gql_params.context,
        variable_values={"id": "", "address": str(address), "description": ""},
    )

    assert not result.errors
    assert result.data["IpamIPAddressUpsert"]["ok"]
    assert not result.data["IpamIPAddressUpsert"]["object"]["description"]["value"]

    address_id = result.data["IpamIPAddressUpsert"]["object"]["id"]
    result = await graphql(
        schema=gql_params.schema,
        source=UPSERT_IPADDRESS,
        context_value=gql_params.context,
        variable_values={"id": address_id, "address": str(address), "description": "RFC 5735"},
    )

    assert not result.errors
    assert result.data["IpamIPAddressUpsert"]["ok"]
    assert result.data["IpamIPAddressUpsert"]["object"]["description"]["value"] == "RFC 5735"


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


GET_PREFIX_HIERARCHY = """
query GetPrefixHierarchy($prefix: String!) {
    IpamIPPrefix(prefix__value: $prefix) {
        edges {
            node {
                id
                prefix { value }
                ancestors { edges { node { id } } }
                parent { node { id } }
                children { edges { node { id } } }
                descendants { edges { node { id } } }
            }
        }
    }
}
"""


async def test_prefix_ancestors_descendants(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)

    ns1 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns1.new(db=db, name="ns1")
    await ns1.save(db=db)
    net8 = await Node.init(db=db, schema=prefix_schema)
    await net8.new(db=db, prefix="10.0.0.0/8", ip_namespace=ns1)
    await net8.save(db=db)
    net10 = await Node.init(db=db, schema=prefix_schema)
    await net10.new(db=db, prefix="10.0.0.0/10", parent=net8, ip_namespace=ns1)
    await net10.save(db=db)
    net12 = await Node.init(db=db, schema=prefix_schema)
    await net12.new(db=db, prefix="10.0.0.0/12", parent=net10, ip_namespace=ns1)
    await net12.save(db=db)
    net14 = await Node.init(db=db, schema=prefix_schema)
    await net14.new(db=db, prefix="10.0.0.0/14", parent=net12, ip_namespace=ns1)
    await net14.save(db=db)
    net16 = await Node.init(db=db, schema=prefix_schema)
    await net16.new(db=db, prefix="10.0.0.0/16", parent=net14, ip_namespace=ns1)
    await net16.save(db=db)

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    check_before = await graphql(
        schema=gql_params.schema,
        source=GET_PREFIX_HIERARCHY,
        context_value=gql_params.context,
        variable_values={"prefix": str(net12.prefix.value)},
    )
    assert not check_before.errors
    assert len(check_before.data["IpamIPPrefix"]["edges"]) == 1
    prefix_details = check_before.data["IpamIPPrefix"]["edges"][0]["node"]
    assert prefix_details["id"] == net12.id
    assert prefix_details["prefix"]["value"] == net12.prefix.value
    ancestors = prefix_details["ancestors"]["edges"]
    assert len(ancestors) == 2
    assert {"node": {"id": net8.id}} in ancestors
    assert {"node": {"id": net10.id}} in ancestors
    parent = prefix_details["parent"]
    assert parent == {"node": {"id": net10.id}}
    children = prefix_details["children"]["edges"]
    assert len(children) == 1
    assert {"node": {"id": net14.id}} in children
    descendants = prefix_details["descendants"]["edges"]
    assert len(descendants) == 2
    assert {"node": {"id": net14.id}} in descendants
    assert {"node": {"id": net16.id}} in descendants

    delete_middle = await graphql(
        schema=gql_params.schema,
        source=DELETE_IPPREFIX,
        context_value=gql_params.context,
        variable_values={"id": str(net12.id)},
    )
    assert not delete_middle.errors
    assert delete_middle.data["IpamIPPrefixDelete"]["ok"] is True

    check_previous_parent = await graphql(
        schema=gql_params.schema,
        source=GET_PREFIX_HIERARCHY,
        context_value=gql_params.context,
        variable_values={"prefix": str(net10.prefix.value)},
    )

    assert not check_previous_parent.errors
    assert len(check_previous_parent.data["IpamIPPrefix"]["edges"]) == 1
    prefix_details = check_previous_parent.data["IpamIPPrefix"]["edges"][0]["node"]
    assert prefix_details["id"] == net10.id
    assert prefix_details["prefix"]["value"] == net10.prefix.value
    ancestors = prefix_details["ancestors"]["edges"]
    assert ancestors == [{"node": {"id": net8.id}}]
    parent = prefix_details["parent"]
    assert parent == {"node": {"id": net8.id}}
    children = prefix_details["children"]["edges"]
    assert children == [{"node": {"id": net14.id}}]
    descendants = prefix_details["descendants"]["edges"]
    assert len(descendants) == 2
    assert {"node": {"id": net14.id}} in descendants
    assert {"node": {"id": net16.id}} in descendants

    check_previous_child = await graphql(
        schema=gql_params.schema,
        source=GET_PREFIX_HIERARCHY,
        context_value=gql_params.context,
        variable_values={"prefix": str(net14.prefix.value)},
    )

    assert not check_previous_child.errors
    assert len(check_previous_child.data["IpamIPPrefix"]["edges"]) == 1
    prefix_details = check_previous_child.data["IpamIPPrefix"]["edges"][0]["node"]
    assert prefix_details["id"] == net14.id
    assert prefix_details["prefix"]["value"] == net14.prefix.value
    ancestors = prefix_details["ancestors"]["edges"]
    assert len(ancestors) == 2
    assert {"node": {"id": net8.id}} in ancestors
    assert {"node": {"id": net10.id}} in ancestors
    parent = prefix_details["parent"]
    assert parent == {"node": {"id": net10.id}}
    children = prefix_details["children"]["edges"]
    assert children == [{"node": {"id": net16.id}}]
    descendants = prefix_details["descendants"]["edges"]
    assert descendants == [{"node": {"id": net16.id}}]
