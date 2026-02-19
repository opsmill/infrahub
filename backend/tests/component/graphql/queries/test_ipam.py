from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, InfrahubKind
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql
from tests.helpers.test_app import TestInfrahubApp


@pytest.fixture
async def ip_dataset_01(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
) -> dict[str, Any]:
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
) -> dict[str, Any]:
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
) -> None:
    obj = ip_dataset_01[prefix]

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

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
) -> None:
    obj = ip_dataset_02[prefix]

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

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


@pytest.fixture(scope="class")
def alternative_ipam_schema() -> SchemaRoot:
    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "IPPrefix",
                "namespace": "Test",
                "default_filter": "prefix__value",
                "order_by": ["prefix__value"],
                "display_labels": ["prefix__value"],
                "branch": BranchSupportType.AWARE.value,
                "inherit_from": [InfrahubKind.IPPREFIX, InfrahubKind.WEIGHTED_POOL_RESOURCE],
            },
            {
                "name": "IPAddress",
                "namespace": "Test",
                "default_filter": "address__value",
                "order_by": ["address__value"],
                "display_labels": ["address__value"],
                "branch": BranchSupportType.AWARE.value,
                "inherit_from": [InfrahubKind.IPADDRESS],
            },
        ],
    }

    return SchemaRoot(**SCHEMA)


class TestIpamAvailableNodes(TestInfrahubApp):
    async def _create_address(
        self, db: InfrahubDatabase, schema: NodeSchema, address: str, ns: Node, prefix: Node
    ) -> None:
        node = await Node.init(db=db, schema=schema)
        await node.new(db=db, address=address, ip_namespace=ns, ip_prefix=prefix)
        await node.save(db=db)

    async def _create_prefix(
        self, db: InfrahubDatabase, schema: NodeSchema, prefix: str, ns: Node, parent: Node
    ) -> None:
        node = await Node.init(db=db, schema=schema)
        await node.new(db=db, prefix=prefix, ip_namespace=ns, parent=parent)
        await node.save(db=db)

    @pytest.fixture(scope="class")
    async def register_ipam_schema(
        self,
        initialize_registry: None,
        default_branch: Branch,
        ipam_schema: SchemaRoot,
        alternative_ipam_schema: SchemaRoot,
    ) -> SchemaBranch:
        schema_branch = registry.schema.register_schema(
            schema=ipam_schema.merge(alternative_ipam_schema), branch=default_branch.name
        )
        default_branch.update_schema_hash()
        return schema_branch

    @pytest.fixture(scope="class")
    async def ip_dataset_ranges(
        self, db: InfrahubDatabase, default_branch: Branch, register_ipam_schema: SchemaBranch
    ) -> dict[str, Any]:
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

        await self._create_address(db, address_schema, "10.0.1.1/29", ns, net_free_end)
        await self._create_address(db, address_schema, "10.0.1.2/29", ns, net_free_end)
        await self._create_address(db, address_schema, "10.0.1.3/29", ns, net_free_end)

        # Prefix with IP available at the beginning
        net_free_start = await Node.init(db=db, schema=prefix_schema)
        await net_free_start.new(db=db, prefix="10.0.2.0/29", ip_namespace=ns, is_pool=False, member_type="address")
        await net_free_start.save(db=db)

        await self._create_address(db, address_schema, "10.0.2.4/29", ns, net_free_start)
        await self._create_address(db, address_schema, "10.0.2.5/29", ns, net_free_start)

        # Prefix with IP available at the beginning and end
        net_free_edges = await Node.init(db=db, schema=prefix_schema)
        await net_free_edges.new(db=db, prefix="10.0.3.0/29", ip_namespace=ns, is_pool=False, member_type="address")
        await net_free_edges.save(db=db)

        await self._create_address(db, address_schema, "10.0.3.3/29", ns, net_free_edges)
        await self._create_address(db, address_schema, "10.0.3.4/29", ns, net_free_edges)

        # Prefix with IP available in the middle
        net_free_middle = await Node.init(db=db, schema=prefix_schema)
        await net_free_middle.new(db=db, prefix="10.0.4.0/29", ip_namespace=ns, is_pool=False, member_type="address")
        await net_free_middle.save(db=db)

        await self._create_address(db, address_schema, "10.0.4.1/29", ns, net_free_middle)
        await self._create_address(db, address_schema, "10.0.4.4/29", ns, net_free_middle)

        # Full prefix
        net_full = await Node.init(db=db, schema=prefix_schema)
        await net_full.new(db=db, prefix="10.0.5.0/29", ip_namespace=ns, is_pool=False, member_type="address")
        await net_full.save(db=db)

        await self._create_address(db, address_schema, "10.0.5.1/29", ns, net_full)
        await self._create_address(db, address_schema, "10.0.5.2/29", ns, net_full)
        await self._create_address(db, address_schema, "10.0.5.3/29", ns, net_full)
        await self._create_address(db, address_schema, "10.0.5.4/29", ns, net_full)
        await self._create_address(db, address_schema, "10.0.5.5/29", ns, net_full)
        await self._create_address(db, address_schema, "10.0.5.6/29", ns, net_full)

        # IPv6 with lots of free IPs
        net6 = await Node.init(db=db, schema=prefix_schema)
        await net6.new(db=db, prefix="2001:db8::/64", ip_namespace=ns, is_pool=False, member_type="address")
        await net6.save(db=db)

        await self._create_address(db, address_schema, "2001:db8::1/64", ns, net6)
        await self._create_address(db, address_schema, "2001:db8::2/64", ns, net6)
        await self._create_address(db, address_schema, "2001:db8::1f/64", ns, net6)
        await self._create_address(db, address_schema, "2001:db8::ff/64", ns, net6)
        await self._create_address(db, address_schema, "2001:db8::100:1/64", ns, net6)
        await self._create_address(db, address_schema, "2001:db8::ffff:ffff:ffff:ffff/64", ns, net6)

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

    @pytest.fixture(scope="class")
    async def ip_dataset_available_prefixes(
        self, db: InfrahubDatabase, default_branch: Branch, register_ipam_schema: SchemaBranch
    ) -> dict[str, Any]:
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

        await self._create_prefix(db, prefix_schema, "10.0.1.0/27", ns, net_free_end)

        # Prefix with availability at the beginning
        net_free_start = await Node.init(db=db, schema=prefix_schema)
        await net_free_start.new(db=db, prefix="10.0.2.0/24", ip_namespace=ns, is_pool=False, member_type="prefix")
        await net_free_start.save(db=db)

        await self._create_prefix(db, prefix_schema, "10.0.2.128/25", ns, net_free_start)

        # Prefix with availability at the beginning and end
        net_free_edges = await Node.init(db=db, schema=prefix_schema)
        await net_free_edges.new(db=db, prefix="10.0.3.0/24", ip_namespace=ns, is_pool=False, member_type="prefix")
        await net_free_edges.save(db=db)

        await self._create_prefix(db, prefix_schema, "10.0.3.128/26", ns, net_free_edges)

        # Prefix with availability in the middle
        net_free_middle = await Node.init(db=db, schema=prefix_schema)
        await net_free_middle.new(db=db, prefix="10.0.4.0/24", ip_namespace=ns, is_pool=False, member_type="prefix")
        await net_free_middle.save(db=db)

        await self._create_prefix(db, prefix_schema, "10.0.4.0/27", ns, net_free_middle)
        await self._create_prefix(db, prefix_schema, "10.0.4.224/27", ns, net_free_middle)

        # Full prefix
        net_full = await Node.init(db=db, schema=prefix_schema)
        await net_full.new(db=db, prefix="10.0.5.0/24", ip_namespace=ns, is_pool=False, member_type="prefix")
        await net_full.save(db=db)

        await self._create_prefix(db, prefix_schema, "10.0.5.0/25", ns, net_full)
        await self._create_prefix(db, prefix_schema, "10.0.5.128/25", ns, net_full)

        # IPv6 with lots of free IPs
        net6 = await Node.init(db=db, schema=prefix_schema)
        await net6.new(db=db, prefix="2001:db8::/48", ip_namespace=ns, is_pool=False, member_type="address")
        await net6.save(db=db)

        await self._create_prefix(db, prefix_schema, "2001:db8::/56", ns, net6)
        await self._create_prefix(db, prefix_schema, "2001:db8:0:a00::/56", ns, net6)
        await self._create_prefix(db, prefix_schema, "2001:db8:0:f000::/64", ns, net6)
        await self._create_prefix(db, prefix_schema, "2001:db8:0:f100::/64", ns, net6)
        await self._create_prefix(db, prefix_schema, "2001:db8:0:f200::/64", ns, net6)
        await self._create_prefix(db, prefix_schema, "2001:db8:0:ff00::/64", ns, net6)
        await self._create_prefix(db, prefix_schema, "2001:db8:0:ffff::/64", ns, net6)

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

    @pytest.fixture(scope="class")
    async def ip_dataset_range_various_kinds(
        self, db: InfrahubDatabase, default_branch: Branch, register_ipam_schema: SchemaBranch
    ) -> dict[str, Any]:
        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
        address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)
        alternative_address_schema = registry.schema.get_node_schema(name="TestIPAddress", branch=default_branch)

        ns = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
        await ns.new(db=db, name="multi-kinds")
        await ns.save(db=db)

        # Prefix with all IP available
        net = await Node.init(db=db, schema=prefix_schema)
        await net.new(db=db, prefix="192.0.2.0/24", ip_namespace=ns, is_pool=False, member_type="address")
        await net.save(db=db)

        ipamipaddress_count = 0
        testipaddress_count = 0
        for i in range(1, 32):
            await self._create_address(db, address_schema, f"192.0.2.{i}/24", ns, net)
            ipamipaddress_count += 1
        for i in range(64, 96):
            await self._create_address(db, alternative_address_schema, f"192.0.2.{i}/24", ns, net)
            testipaddress_count += 1
        for i in range(96, 128):
            await self._create_address(db, address_schema, f"192.0.2.{i}/24", ns, net)
            ipamipaddress_count += 1

        return {
            "ns": ns,
            "net": net,
            "ipamipaddress_count": ipamipaddress_count,
            "testipaddress_count": testipaddress_count,
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
                    ("InternalIPRangeAvailable", "More than 65536 IP addresses available"),
                    ("IpamIPAddress", "2001:db8::100:1/64"),
                    ("InternalIPRangeAvailable", "More than 65536 IP addresses available"),
                    ("IpamIPAddress", "2001:db8::ffff:ffff:ffff:ffff/64"),
                ],
            ),
        ],
    )
    async def test_ipaddress_include_available(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        default_ipnamespace: Node,
        register_ipam_schema: SchemaBranch,
        ip_dataset_ranges: dict[str, Node],
        prefix: str,
        result: list[str],
    ) -> None:
        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)

        query = """
        query($prefix: ID!) {
            BuiltinIPAddress(ip_prefix__ids: [$prefix], include_available: true) {
                edges {
                    node {
                        id
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
            variable_values={"prefix": ip_dataset_ranges[prefix].id},
        )
        assert not response.errors
        assert response.data
        assert response.data["BuiltinIPAddress"]["edges"]
        assert result == [
            (node["node"]["__typename"], node["node"]["display_label"])
            for node in response.data["BuiltinIPAddress"]["edges"]
        ]

    @pytest.mark.parametrize(
        "limit,kinds",
        [
            (0, ["IpamIPAddress"]),
            (0, ["IpamIPAddress", "TestIPAddress"]),
            (10, ["IpamIPAddress"]),
            (10, ["IpamIPAddress", "TestIPAddress"]),
            (60, ["IpamIPAddress"]),
            (60, ["IpamIPAddress", "TestIPAddress"]),
        ],
    )
    async def test_ip_address_include_available_filtered_by_kind(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        default_ipnamespace: Node,
        register_ipam_schema: SchemaBranch,
        ip_dataset_range_various_kinds: dict[str, Node],
        limit: int,
        kinds: list[str],
    ) -> None:
        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        query = """
        query($prefix: ID!, $limit: Int!, $kinds: [String!]) {
            BuiltinIPAddress(ip_prefix__ids: [$prefix], include_available: true, kinds: $kinds, limit: $limit) {
                edges {
                    node {
                        id
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
            variable_values={"prefix": ip_dataset_range_various_kinds["net"].id, "limit": limit, "kinds": kinds},
        )
        assert not response.errors
        assert response.data
        assert response.data["BuiltinIPAddress"]["edges"]

        if len(kinds) == 1 or (limit > 0 and limit < 32):
            # There should be only one kind if we exclude available range
            assert {node["node"]["__typename"] for node in response.data["BuiltinIPAddress"]["edges"]} - {
                "InternalIPRangeAvailable"
            } == {"IpamIPAddress"}
        else:
            assert {node["node"]["__typename"] for node in response.data["BuiltinIPAddress"]["edges"]} - {
                "InternalIPRangeAvailable"
            } == set(kinds)

        expected_ipaddress_count = ip_dataset_range_various_kinds["ipamipaddress_count"]
        if len(kinds) == 2:
            expected_ipaddress_count += ip_dataset_range_various_kinds["testipaddress_count"]

        # Given the used fixture, only 0, 1 or 2 available ranges can be in the result
        if limit:
            assert len(response.data["BuiltinIPAddress"]["edges"]) - limit in [0, 1, 2]
        else:
            # If we query for all addresses, we'll have 2 available ranges too
            assert len(response.data["BuiltinIPAddress"]["edges"]) == expected_ipaddress_count + 2

    async def test_ip_address_include_available_filtered_by_kind_invalid(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        default_ipnamespace: Node,
        register_ipam_schema: SchemaBranch,
        ip_dataset_range_various_kinds: dict[str, Node],
    ) -> None:
        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)
        query = """
        query($prefix: ID!, $kinds: [String!]) {
            BuiltinIPAddress(ip_prefix__ids: [$prefix], include_available: true, kinds: $kinds) {
                edges {
                    node {
                        id
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
            variable_values={"prefix": ip_dataset_range_various_kinds["net"].id, "kinds": ["NotAnIPAddress"]},
        )

        assert response.errors
        assert response.errors[0].message == "NotAnIPAddress is not a node inheriting from BuiltinIPAddress"

    @pytest.mark.parametrize(
        "limit,offset,result",
        [
            (
                1,
                0,
                [
                    ("InternalIPRangeAvailable", "1 IP address available"),
                    ("IpamIPAddress", "2001:db8::1/64"),
                ],
            ),
            (
                2,
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
                0,
                [
                    ("InternalIPRangeAvailable", "1 IP address available"),
                    ("IpamIPAddress", "2001:db8::1/64"),
                    ("IpamIPAddress", "2001:db8::2/64"),
                    ("InternalIPRangeAvailable", "28 IP addresses available"),
                    ("IpamIPAddress", "2001:db8::1f/64"),
                    ("InternalIPRangeAvailable", "223 IP addresses available"),
                    ("IpamIPAddress", "2001:db8::ff/64"),
                    ("InternalIPRangeAvailable", "More than 65536 IP addresses available"),
                ],
            ),
            (
                0,
                2,
                [
                    ("InternalIPRangeAvailable", "28 IP addresses available"),
                    ("IpamIPAddress", "2001:db8::1f/64"),
                    ("InternalIPRangeAvailable", "223 IP addresses available"),
                    ("IpamIPAddress", "2001:db8::ff/64"),
                    ("InternalIPRangeAvailable", "More than 65536 IP addresses available"),
                    ("IpamIPAddress", "2001:db8::100:1/64"),
                    ("InternalIPRangeAvailable", "More than 65536 IP addresses available"),
                    ("IpamIPAddress", "2001:db8::ffff:ffff:ffff:ffff/64"),
                ],
            ),
            (
                4,
                4,
                [
                    ("InternalIPRangeAvailable", "More than 65536 IP addresses available"),
                    ("IpamIPAddress", "2001:db8::100:1/64"),
                    ("InternalIPRangeAvailable", "More than 65536 IP addresses available"),
                    ("IpamIPAddress", "2001:db8::ffff:ffff:ffff:ffff/64"),
                ],
            ),
            (
                5,
                6,
                [
                    ("InternalIPRangeAvailable", "More than 65536 IP addresses available"),
                    ("IpamIPAddress", "2001:db8::ffff:ffff:ffff:ffff/64"),
                ],
            ),
        ],
    )
    async def test_ipaddress_include_available_pagination(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        default_ipnamespace: Node,
        register_ipam_schema: SchemaBranch,
        ip_dataset_ranges: dict[str, Node],
        limit: int,
        offset: int,
        result: list[str],
    ) -> None:
        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)

        query = """
        query($prefix: ID!, $limit: Int!, $offset: Int!) {
            BuiltinIPAddress(ip_prefix__ids: [$prefix], include_available: true, limit: $limit, offset: $offset) {
                edges {
                    node {
                        id
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
            variable_values={"prefix": ip_dataset_ranges["net6"].id, "limit": limit, "offset": offset},
        )
        assert not response.errors
        assert response.data
        assert response.data["BuiltinIPAddress"]["edges"]
        assert result == [
            (node["node"]["__typename"], node["node"]["display_label"])
            for node in response.data["BuiltinIPAddress"]["edges"]
        ]

    @pytest.mark.parametrize(
        "prefix,result",
        [
            (
                "net_empty",
                [("InternalIPPrefixAvailable", "10.0.0.0/25"), ("InternalIPPrefixAvailable", "10.0.0.128/25")],
            ),
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
                    ("IpamIPPrefix", "2001:db8:0:f100::/64"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f101::/64"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f102::/63"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f104::/62"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f108::/61"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f110::/60"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f120::/59"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f140::/58"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f180::/57"),
                    ("IpamIPPrefix", "2001:db8:0:f200::/64"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f201::/64"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f202::/63"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f204::/62"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f208::/61"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f210::/60"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f220::/59"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f240::/58"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f280::/57"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f300::/56"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f400::/54"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f800::/54"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:fc00::/55"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:fe00::/56"),
                    ("IpamIPPrefix", "2001:db8:0:ff00::/64"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff01::/64"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff02::/63"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff04::/62"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff08::/61"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff10::/60"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff20::/59"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff40::/58"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff80::/58"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ffc0::/59"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ffe0::/60"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:fff0::/61"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:fff8::/62"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:fffc::/63"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:fffe::/64"),
                    ("IpamIPPrefix", "2001:db8:0:ffff::/64"),
                ],
            ),
        ],
    )
    async def test_ipprefix_include_available(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        default_ipnamespace: Node,
        register_ipam_schema: SchemaBranch,
        ip_dataset_available_prefixes: dict[str, Node],
        prefix: str,
        result: list[str],
    ) -> None:
        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)

        query = """
        query($prefix: ID!) {
            BuiltinIPPrefix(parent__ids: [$prefix], include_available: true) {
                edges {
                    node {
                        id
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
            variable_values={"prefix": ip_dataset_available_prefixes[prefix].id},
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
                    ("IpamIPPrefix", "2001:db8:0:f100::/64"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f101::/64"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f102::/63"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f104::/62"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f108::/61"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f110::/60"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f120::/59"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f140::/58"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f180::/57"),
                ],
            ),
            (
                2,
                1,
                [
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
            (
                20,
                4,
                [
                    ("InternalIPPrefixAvailable", "2001:db8:0:f101::/64"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f102::/63"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f104::/62"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f108::/61"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f110::/60"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f120::/59"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f140::/58"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f180::/57"),
                    ("IpamIPPrefix", "2001:db8:0:f200::/64"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f201::/64"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f202::/63"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f204::/62"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f208::/61"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f210::/60"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f220::/59"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f240::/58"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f280::/57"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f300::/56"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f400::/54"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:f800::/54"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:fc00::/55"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:fe00::/56"),
                    ("IpamIPPrefix", "2001:db8:0:ff00::/64"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff01::/64"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff02::/63"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff04::/62"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff08::/61"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff10::/60"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff20::/59"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff40::/58"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ff80::/58"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ffc0::/59"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:ffe0::/60"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:fff0::/61"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:fff8::/62"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:fffc::/63"),
                    ("InternalIPPrefixAvailable", "2001:db8:0:fffe::/64"),
                    ("IpamIPPrefix", "2001:db8:0:ffff::/64"),
                ],
            ),
        ],
    )
    async def test_ipprefix_include_available_pagination(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        default_ipnamespace: Node,
        register_ipam_schema: SchemaBranch,
        ip_dataset_available_prefixes: dict[str, Node],
        limit: int,
        offset: int,
        result: list[str],
    ) -> None:
        default_branch.update_schema_hash()
        gql_params = await prepare_graphql_params(db=db, branch=default_branch)

        query = """
        query($prefix: ID!, $limit: Int!, $offset: Int!) {
            BuiltinIPPrefix(parent__ids: [$prefix], include_available: true, limit: $limit, offset: $offset) {
                edges {
                    node {
                        id
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
            variable_values={"prefix": ip_dataset_available_prefixes["net6"].id, "limit": limit, "offset": offset},
        )

        assert not response.errors
        assert response.data
        assert response.data["BuiltinIPPrefix"]["edges"]
        assert result == [
            (node["node"]["__typename"], node["node"]["display_label"])
            for node in response.data["BuiltinIPPrefix"]["edges"]
        ]
