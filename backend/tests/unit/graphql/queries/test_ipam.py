import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql


@pytest.fixture
async def ip_dataset_01(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)

    # -----------------------
    # Namespace NS1
    # -----------------------

    ns1 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns1.new(db=db, name="ns1")
    await ns1.save(db=db)

    net146 = await Node.init(db=db, schema=prefix_schema)
    await net146.new(db=db, prefix="10.0.0.0/8", ip_namespace=ns1)
    await net146.save(db=db)

    net140 = await Node.init(db=db, schema=prefix_schema)
    await net140.new(db=db, prefix="10.10.0.0/16", ip_namespace=ns1, parent=net146)
    await net140.save(db=db)

    net142 = await Node.init(db=db, schema=prefix_schema)
    await net142.new(db=db, prefix="10.10.1.0/24", parent=net140, ip_namespace=ns1)
    await net142.save(db=db)

    net143 = await Node.init(db=db, schema=prefix_schema)
    await net143.new(db=db, prefix="10.10.1.0/27", parent=net142, ip_namespace=ns1)
    await net143.save(db=db)

    net144 = await Node.init(db=db, schema=prefix_schema)
    await net144.new(db=db, prefix="10.10.2.0/24", parent=net140, ip_namespace=ns1)
    await net144.save(db=db)

    net145 = await Node.init(db=db, schema=prefix_schema)
    await net145.new(db=db, prefix="10.10.3.0/27", parent=net140, ip_namespace=ns1)
    await net145.save(db=db)

    data = {
        "ns1": ns1,
        # "ns2": ns2,
        # "net161": net161,
        # "net162": net162,
        "net140": net140,
        "net142": net142,
        "net143": net143,
        "net144": net144,
        "net145": net145,
        "net146": net146,
        # "address10": address10,
        # "address11": address11,
        # "net240": net240,
        # "net241": net241,
        # "net242": net242,
    }
    return data


@pytest.fixture
async def ip_dataset_02(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

    # -----------------------
    # Namespace NS1
    # -----------------------

    ns = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns.new(db=db, name="ns2")
    await ns.save(db=db)

    net1 = await Node.init(db=db, schema=prefix_schema)
    await net1.new(db=db, prefix="10.200.30.0/27", ip_namespace=ns, is_pool=False, member_type="address")
    await net1.save(db=db)

    net1_ip1 = await Node.init(db=db, schema=address_schema)
    await net1_ip1.new(db=db, address="10.200.30.1/27", ip_namespace=ns, ip_prefix=net1)
    await net1_ip1.save(db=db)

    data = {
        "ns": ns,
        "net1": net1,
    }
    return data


@pytest.mark.parametrize(
    "prefix,prefix_length,response",
    [
        ("net146", 16, "10.0.0.0/16"),
        ("net146", 24, "10.0.0.0/24"),
        ("net142", 26, "10.10.1.64/26"),
        ("net142", None, "10.10.1.32/27"),
    ],
)
async def test_ipprefix_nextavailable(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_01,
    prefix,
    prefix_length,
    response,
):
    obj = ip_dataset_01[prefix]

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    query = """
    query($prefix: String!, $prefix_length: Int) {
        InfrahubIPPrefixGetNextAvailable(prefix_id: $prefix, prefix_length: $prefix_length) {
            prefix
        }
    }
    """

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        variable_values={"prefix": obj.id, "prefix_length": prefix_length},
    )

    assert not result.errors
    assert result.data
    assert result.data["InfrahubIPPrefixGetNextAvailable"]["prefix"] == response


@pytest.mark.parametrize(
    "prefix,prefix_length,response",
    [
        ("net1", 30, "10.200.30.2/30"),
        ("net1", None, "10.200.30.2/27"),
    ],
)
async def test_ipaddress_nextavailable(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_02,
    prefix,
    prefix_length,
    response,
):
    obj = ip_dataset_02[prefix]

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    query = """
    query($prefix: String!, $prefix_length: Int) {
        InfrahubIPAddressGetNextAvailable(prefix_id: $prefix, prefix_length: $prefix_length) {
            address
        }
    }
    """

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        variable_values={"prefix": obj.id, "prefix_length": prefix_length},
    )

    assert not result.errors
    assert result.data
    assert result.data["InfrahubIPAddressGetNextAvailable"]["address"] == response


async def _create_address(db: InfrahubDatabase, schema: NodeSchema, address: str, ns: Node, prefix: Node) -> None:
    node = await Node.init(db=db, schema=schema)
    await node.new(db=db, address=address, ip_namespace=ns, ip_prefix=prefix)
    await node.save(db=db)


async def _create_prefix(db: InfrahubDatabase, schema: NodeSchema, prefix: str, ns: Node, parent: Node) -> None:
    node = await Node.init(db=db, schema=schema)
    await node.new(db=db, prefix=prefix, ip_namespace=ns, parent=parent)
    await node.save(db=db)


@pytest.fixture
async def ip_dataset_ranges(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

    ns = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns.new(db=db, name="ns-ranges")
    await ns.save(db=db)

    # Prefix with all IP available
    net_all_free = await Node.init(db=db, schema=prefix_schema)
    await net_all_free.new(db=db, prefix="10.0.0.0/29", ip_namespace=ns, is_pool=False, member_type="address")
    await net_all_free.save(db=db)

    # Prefix with IP available at the end
    net_free_end = await Node.init(db=db, schema=prefix_schema)
    await net_free_end.new(db=db, prefix="10.0.1.0/29", ip_namespace=ns, is_pool=False, member_type="address")
    await net_free_end.save(db=db)

    await _create_address(db, address_schema, "10.0.1.1/29", ns, net_free_end)
    await _create_address(db, address_schema, "10.0.1.2/29", ns, net_free_end)
    await _create_address(db, address_schema, "10.0.1.3/29", ns, net_free_end)

    # Prefix with IP available at the beginning
    net_free_start = await Node.init(db=db, schema=prefix_schema)
    await net_free_start.new(db=db, prefix="10.0.2.0/29", ip_namespace=ns, is_pool=False, member_type="address")
    await net_free_start.save(db=db)

    await _create_address(db, address_schema, "10.0.2.4/29", ns, net_free_start)
    await _create_address(db, address_schema, "10.0.2.5/29", ns, net_free_start)

    # Prefix with IP available at the beginning and end
    net_free_edges = await Node.init(db=db, schema=prefix_schema)
    await net_free_edges.new(db=db, prefix="10.0.3.0/29", ip_namespace=ns, is_pool=False, member_type="address")
    await net_free_edges.save(db=db)

    await _create_address(db, address_schema, "10.0.3.3/29", ns, net_free_edges)
    await _create_address(db, address_schema, "10.0.3.4/29", ns, net_free_edges)

    # Prefix with IP available in the middle
    net_free_middle = await Node.init(db=db, schema=prefix_schema)
    await net_free_middle.new(db=db, prefix="10.0.4.0/29", ip_namespace=ns, is_pool=False, member_type="address")
    await net_free_middle.save(db=db)

    await _create_address(db, address_schema, "10.0.4.1/29", ns, net_free_middle)
    await _create_address(db, address_schema, "10.0.4.4/29", ns, net_free_middle)

    # Full prefix
    net_full = await Node.init(db=db, schema=prefix_schema)
    await net_full.new(db=db, prefix="10.0.5.0/29", ip_namespace=ns, is_pool=False, member_type="address")
    await net_full.save(db=db)

    await _create_address(db, address_schema, "10.0.5.1/29", ns, net_full)
    await _create_address(db, address_schema, "10.0.5.2/29", ns, net_full)
    await _create_address(db, address_schema, "10.0.5.3/29", ns, net_full)
    await _create_address(db, address_schema, "10.0.5.4/29", ns, net_full)
    await _create_address(db, address_schema, "10.0.5.5/29", ns, net_full)
    await _create_address(db, address_schema, "10.0.5.6/29", ns, net_full)

    # IPv6 with lots of free IPs
    net6 = await Node.init(db=db, schema=prefix_schema)
    await net6.new(db=db, prefix="2001:db8::/64", ip_namespace=ns, is_pool=False, member_type="address")
    await net6.save(db=db)

    await _create_address(db, address_schema, "2001:db8::1/64", ns, net6)
    await _create_address(db, address_schema, "2001:db8::2/64", ns, net6)
    await _create_address(db, address_schema, "2001:db8::1f/64", ns, net6)
    await _create_address(db, address_schema, "2001:db8::ff/64", ns, net6)
    await _create_address(db, address_schema, "2001:db8::100:1/64", ns, net6)
    await _create_address(db, address_schema, "2001:db8::ffff:ffff:ffff:ffff/64", ns, net6)

    return {
        "ns": ns,
        "net_all_free": net_all_free,
        "net_free_end": net_free_end,
        "net_free_start": net_free_start,
        "net_free_edges": net_free_edges,
        "net_free_middle": net_free_middle,
        "net_full": net_full,
        "net6": net6,
    }


@pytest.mark.parametrize(
    "prefix,result",
    [
        ("net_all_free", [("InternalIPRangeAvailable", "6 IP addresses available")]),
        (
            "net_free_end",
            [
                ("IpamIPAddress", "10.0.1.1/29"),
                ("IpamIPAddress", "10.0.1.2/29"),
                ("IpamIPAddress", "10.0.1.3/29"),
                ("InternalIPRangeAvailable", "3 IP addresses available"),
            ],
        ),
        (
            "net_free_start",
            [
                ("InternalIPRangeAvailable", "3 IP addresses available"),
                ("IpamIPAddress", "10.0.2.4/29"),
                ("IpamIPAddress", "10.0.2.5/29"),
                ("InternalIPRangeAvailable", "1 IP address available"),
            ],
        ),
        (
            "net_free_edges",
            [
                ("InternalIPRangeAvailable", "2 IP addresses available"),
                ("IpamIPAddress", "10.0.3.3/29"),
                ("IpamIPAddress", "10.0.3.4/29"),
                ("InternalIPRangeAvailable", "2 IP addresses available"),
            ],
        ),
        (
            "net_free_middle",
            [
                ("IpamIPAddress", "10.0.4.1/29"),
                ("InternalIPRangeAvailable", "2 IP addresses available"),
                ("IpamIPAddress", "10.0.4.4/29"),
                ("InternalIPRangeAvailable", "2 IP addresses available"),
            ],
        ),
        (
            "net_full",
            [
                ("IpamIPAddress", "10.0.5.1/29"),
                ("IpamIPAddress", "10.0.5.2/29"),
                ("IpamIPAddress", "10.0.5.3/29"),
                ("IpamIPAddress", "10.0.5.4/29"),
                ("IpamIPAddress", "10.0.5.5/29"),
                ("IpamIPAddress", "10.0.5.6/29"),
            ],
        ),
        (
            "net6",
            [
                ("InternalIPRangeAvailable", "1 IP address available"),
                ("IpamIPAddress", "2001:db8::1/64"),
                ("IpamIPAddress", "2001:db8::2/64"),
                ("InternalIPRangeAvailable", "28 IP addresses available"),
                ("IpamIPAddress", "2001:db8::1f/64"),
                ("InternalIPRangeAvailable", "223 IP addresses available"),
                ("IpamIPAddress", "2001:db8::ff/64"),
                ("InternalIPRangeAvailable", "Many IP addresses available"),
                ("IpamIPAddress", "2001:db8::100:1/64"),
                ("InternalIPRangeAvailable", "Many IP addresses available"),
                ("IpamIPAddress", "2001:db8::ffff:ffff:ffff:ffff/64"),
            ],
        ),
    ],
)
async def test_ipaddress_include_available(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_ranges: dict[str, Node],
    prefix: str,
    result: list[str],
):
    obj = ip_dataset_ranges[prefix]

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    query = """
    query($prefix: ID!) {
        BuiltinIPAddress(ip_prefix__ids: [$prefix], include_available: true) {
            edges {
                node {
                    display_label
                    __typename
                }
            }
        }
    }
    """

    response = await graphql(
        schema=gql_params.schema, source=query, context_value=gql_params.context, variable_values={"prefix": obj.id}
    )
    assert not response.errors
    assert response.data
    assert response.data["BuiltinIPAddress"]["edges"]
    assert result == [
        (node["node"]["__typename"], node["node"]["display_label"])
        for node in response.data["BuiltinIPAddress"]["edges"]
    ]


@pytest.mark.parametrize(
    "limit,offset,result",
    [
        (
            4,
            0,
            [
                ("InternalIPRangeAvailable", "1 IP address available"),
                ("IpamIPAddress", "2001:db8::1/64"),
                ("IpamIPAddress", "2001:db8::2/64"),
                ("InternalIPRangeAvailable", "28 IP addresses available"),
            ],
        ),
        (
            4,
            4,
            [
                ("IpamIPAddress", "2001:db8::1f/64"),
                ("InternalIPRangeAvailable", "223 IP addresses available"),
                ("IpamIPAddress", "2001:db8::ff/64"),
                ("InternalIPRangeAvailable", "Many IP addresses available"),
            ],
        ),
        (
            5,
            6,
            [
                ("IpamIPAddress", "2001:db8::ff/64"),
                ("InternalIPRangeAvailable", "Many IP addresses available"),
                ("IpamIPAddress", "2001:db8::100:1/64"),
                ("InternalIPRangeAvailable", "Many IP addresses available"),
                ("IpamIPAddress", "2001:db8::ffff:ffff:ffff:ffff/64"),
            ],
        ),
    ],
)
async def test_ipaddress_include_available_pagination(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_ranges: dict[str, Node],
    limit: int,
    offset: int,
    result: list[str],
):
    obj = ip_dataset_ranges["net6"]

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    query = """
    query($prefix: ID!, $limit: Int!, $offset: Int!) {
        BuiltinIPAddress(ip_prefix__ids: [$prefix], include_available: true, limit: $limit, offset: $offset) {
            edges {
                node {
                    display_label
                    __typename
                }
            }
        }
    }
    """

    response = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        variable_values={"prefix": obj.id, "limit": limit, "offset": offset},
    )
    assert not response.errors
    assert response.data
    assert response.data["BuiltinIPAddress"]["edges"]
    assert result == [
        (node["node"]["__typename"], node["node"]["display_label"])
        for node in response.data["BuiltinIPAddress"]["edges"]
    ]


@pytest.fixture
async def ip_dataset_available_prefixes(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)

    ns = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns.new(db=db, name="ns-available-prefixes")
    await ns.save(db=db)

    # Empty prefix
    net_empty = await Node.init(db=db, schema=prefix_schema)
    await net_empty.new(db=db, prefix="10.0.0.0/24", ip_namespace=ns, is_pool=False, member_type="prefix")
    await net_empty.save(db=db)

    # Prefix with availability at the end
    net_free_end = await Node.init(db=db, schema=prefix_schema)
    await net_free_end.new(db=db, prefix="10.0.1.0/24", ip_namespace=ns, is_pool=False, member_type="prefix")
    await net_free_end.save(db=db)

    await _create_prefix(db, prefix_schema, "10.0.1.0/27", ns, net_free_end)

    # Prefix with availability at the beginning
    net_free_start = await Node.init(db=db, schema=prefix_schema)
    await net_free_start.new(db=db, prefix="10.0.2.0/24", ip_namespace=ns, is_pool=False, member_type="prefix")
    await net_free_start.save(db=db)

    await _create_prefix(db, prefix_schema, "10.0.2.128/25", ns, net_free_start)

    # Prefix with availability at the beginning and end
    net_free_edges = await Node.init(db=db, schema=prefix_schema)
    await net_free_edges.new(db=db, prefix="10.0.3.0/24", ip_namespace=ns, is_pool=False, member_type="prefix")
    await net_free_edges.save(db=db)

    await _create_prefix(db, prefix_schema, "10.0.3.128/26", ns, net_free_edges)

    # Prefix with availability in the middle
    net_free_middle = await Node.init(db=db, schema=prefix_schema)
    await net_free_middle.new(db=db, prefix="10.0.4.0/24", ip_namespace=ns, is_pool=False, member_type="prefix")
    await net_free_middle.save(db=db)

    await _create_prefix(db, prefix_schema, "10.0.4.0/27", ns, net_free_middle)
    await _create_prefix(db, prefix_schema, "10.0.4.224/27", ns, net_free_middle)

    # Full prefix
    net_full = await Node.init(db=db, schema=prefix_schema)
    await net_full.new(db=db, prefix="10.0.5.0/24", ip_namespace=ns, is_pool=False, member_type="prefix")
    await net_full.save(db=db)

    await _create_prefix(db, prefix_schema, "10.0.5.0/25", ns, net_full)
    await _create_prefix(db, prefix_schema, "10.0.5.128/25", ns, net_full)

    # IPv6 with lots of free IPs
    net6 = await Node.init(db=db, schema=prefix_schema)
    await net6.new(db=db, prefix="2001:db8::/48", ip_namespace=ns, is_pool=False, member_type="address")
    await net6.save(db=db)

    await _create_prefix(db, prefix_schema, "2001:db8::/56", ns, net6)
    await _create_prefix(db, prefix_schema, "2001:db8:0:a00::/56", ns, net6)
    await _create_prefix(db, prefix_schema, "2001:db8:0:f000::/64", ns, net6)

    return {
        "ns": ns,
        "net_empty": net_empty,
        "net_free_end": net_free_end,
        "net_free_start": net_free_start,
        "net_free_edges": net_free_edges,
        "net_free_middle": net_free_middle,
        "net_full": net_full,
        "net6": net6,
    }


@pytest.mark.parametrize(
    "prefix,result",
    [
        ("net_empty", [("InternalIPPrefixAvailable", "10.0.0.0/24")]),
        (
            "net_free_end",
            [
                ("IpamIPPrefix", "10.0.1.0/27"),
                ("InternalIPPrefixAvailable", "10.0.1.32/27"),
                ("InternalIPPrefixAvailable", "10.0.1.64/26"),
                ("InternalIPPrefixAvailable", "10.0.1.128/25"),
            ],
        ),
        ("net_free_start", [("InternalIPPrefixAvailable", "10.0.2.0/25"), ("IpamIPPrefix", "10.0.2.128/25")]),
        (
            "net_free_edges",
            [
                ("InternalIPPrefixAvailable", "10.0.3.0/25"),
                ("IpamIPPrefix", "10.0.3.128/26"),
                ("InternalIPPrefixAvailable", "10.0.3.192/26"),
            ],
        ),
        (
            "net_free_middle",
            [
                ("IpamIPPrefix", "10.0.4.0/27"),
                ("InternalIPPrefixAvailable", "10.0.4.32/27"),
                ("InternalIPPrefixAvailable", "10.0.4.64/26"),
                ("InternalIPPrefixAvailable", "10.0.4.128/26"),
                ("InternalIPPrefixAvailable", "10.0.4.192/27"),
                ("IpamIPPrefix", "10.0.4.224/27"),
            ],
        ),
        ("net_full", [("IpamIPPrefix", "10.0.5.0/25"), ("IpamIPPrefix", "10.0.5.128/25")]),
        (
            "net6",
            [
                ("IpamIPPrefix", "2001:db8::/56"),
                ("InternalIPPrefixAvailable", "2001:db8:0:100::/56"),
                ("InternalIPPrefixAvailable", "2001:db8:0:200::/55"),
                ("InternalIPPrefixAvailable", "2001:db8:0:400::/54"),
                ("InternalIPPrefixAvailable", "2001:db8:0:800::/55"),
                ("IpamIPPrefix", "2001:db8:0:a00::/56"),
                ("InternalIPPrefixAvailable", "2001:db8:0:b00::/56"),
                ("InternalIPPrefixAvailable", "2001:db8:0:c00::/54"),
                ("InternalIPPrefixAvailable", "2001:db8:0:1000::/52"),
                ("InternalIPPrefixAvailable", "2001:db8:0:2000::/51"),
                ("InternalIPPrefixAvailable", "2001:db8:0:4000::/50"),
                ("InternalIPPrefixAvailable", "2001:db8:0:8000::/50"),
                ("InternalIPPrefixAvailable", "2001:db8:0:c000::/51"),
                ("InternalIPPrefixAvailable", "2001:db8:0:e000::/52"),
                ("IpamIPPrefix", "2001:db8:0:f000::/64"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f001::/64"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f002::/63"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f004::/62"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f008::/61"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f010::/60"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f020::/59"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f040::/58"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f080::/57"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f100::/56"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f200::/55"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f400::/54"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f800::/53"),
            ],
        ),
    ],
)
async def test_ipprefix_include_available(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_available_prefixes: dict[str, Node],
    prefix: str,
    result: list[str],
):
    obj = ip_dataset_available_prefixes[prefix]

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    query = """
    query($prefix: ID!) {
        BuiltinIPPrefix(parent__ids: [$prefix], include_available: true) {
            edges {
                node {
                    __typename
                    display_label
                }
            }
        }
    }
    """

    response = await graphql(
        schema=gql_params.schema, source=query, context_value=gql_params.context, variable_values={"prefix": obj.id}
    )

    assert not response.errors
    assert response.data
    assert response.data["BuiltinIPPrefix"]["edges"]
    assert result == [
        (node["node"]["__typename"], node["node"]["display_label"])
        for node in response.data["BuiltinIPPrefix"]["edges"]
    ]


@pytest.mark.parametrize(
    "limit,offset,result",
    [
        (
            4,
            0,
            [
                ("IpamIPPrefix", "2001:db8::/56"),
                ("InternalIPPrefixAvailable", "2001:db8:0:100::/56"),
                ("InternalIPPrefixAvailable", "2001:db8:0:200::/55"),
                ("InternalIPPrefixAvailable", "2001:db8:0:400::/54"),
            ],
        ),
        (
            4,
            4,
            [
                ("InternalIPPrefixAvailable", "2001:db8:0:800::/55"),
                ("IpamIPPrefix", "2001:db8:0:a00::/56"),
                ("InternalIPPrefixAvailable", "2001:db8:0:b00::/56"),
                ("InternalIPPrefixAvailable", "2001:db8:0:c00::/54"),
            ],
        ),
        (
            20,
            8,
            [
                ("InternalIPPrefixAvailable", "2001:db8:0:1000::/52"),
                ("InternalIPPrefixAvailable", "2001:db8:0:2000::/51"),
                ("InternalIPPrefixAvailable", "2001:db8:0:4000::/50"),
                ("InternalIPPrefixAvailable", "2001:db8:0:8000::/50"),
                ("InternalIPPrefixAvailable", "2001:db8:0:c000::/51"),
                ("InternalIPPrefixAvailable", "2001:db8:0:e000::/52"),
                ("IpamIPPrefix", "2001:db8:0:f000::/64"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f001::/64"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f002::/63"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f004::/62"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f008::/61"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f010::/60"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f020::/59"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f040::/58"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f080::/57"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f100::/56"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f200::/55"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f400::/54"),
                ("InternalIPPrefixAvailable", "2001:db8:0:f800::/53"),
            ],
        ),
    ],
)
async def test_ipprefix_include_available_pagination(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_available_prefixes: dict[str, Node],
    limit: int,
    offset: int,
    result: list[str],
):
    obj = ip_dataset_available_prefixes["net6"]

    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    query = """
    query($prefix: ID!, $limit: Int!, $offset: Int!) {
        BuiltinIPPrefix(parent__ids: [$prefix], include_available: true, limit: $limit, offset: $offset) {
            edges {
                node {
                    __typename
                    display_label
                }
            }
        }
    }
    """

    response = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        variable_values={"prefix": obj.id, "limit": limit, "offset": offset},
    )

    assert not response.errors
    assert response.data
    assert response.data["BuiltinIPPrefix"]["edges"]
    assert result == [
        (node["node"]["__typename"], node["node"]["display_label"])
        for node in response.data["BuiltinIPPrefix"]["edges"]
    ]
