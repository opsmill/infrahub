import pytest
from graphql import graphql

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.core.schema_manager import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


@pytest.fixture
async def prefix_pools_02(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry,
    ip_dataset_01,
):
    ns1 = ip_dataset_01["ns1"]
    ipv6_prefix_resource = ip_dataset_01["net161"]
    ipv4_prefix_resource = ip_dataset_01["net144"]
    ipv4_address_resource = ip_dataset_01["net145"]

    prefix_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)
    address_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)

    ipv6_prefix_pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db, branch=default_branch)
    await ipv6_prefix_pool.new(
        db=db,
        name="ipv6_prefix",
        default_prefix_size=56,
        default_prefix_type="IpamIPPrefix",
        resources=[ipv6_prefix_resource],
        ip_namespace=ns1,
    )
    await ipv6_prefix_pool.save(db=db)

    ipv4_prefix_pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db, branch=default_branch)
    await ipv4_prefix_pool.new(
        db=db,
        name="ipv4_prefix",
        default_prefix_size=26,
        default_prefix_type="IpamIPPrefix",
        resources=[ipv4_prefix_resource],
        ip_namespace=ns1,
    )
    await ipv4_prefix_pool.save(db=db)

    ipv4_address_pool = await CoreIPAddressPool.init(schema=address_pool_schema, db=db, branch=default_branch)
    await ipv4_address_pool.new(
        db=db,
        name="ipv4_address",
        default_prefix_length=27,
        default_address_type="IpamIPAddress",
        resources=[ipv4_address_resource],
        ip_namespace=ns1,
    )
    await ipv4_address_pool.save(db=db)

    return {
        "ipv4_address_pool": ipv4_address_pool,
        "ipv4_address_resource": ipv4_address_resource,
        "ipv4_prefix_pool": ipv4_prefix_pool,
        "ipv4_prefix_resource": ipv4_prefix_resource,
        "ipv6_prefix_pool": ipv6_prefix_pool,
        "ipv6_prefix_resource": ipv6_prefix_resource,
    }


ADDRESS_MUTATION = """
mutation CreateAddress($name: String!, $pool: String!, $identifier: String){
    TestMandatoryAddressCreate(data: {
        name: { value: $name }
        address: {
            from_pool: {
                id: $pool
                identifier: $identifier
            }
        }
    }) {
        ok
        object {
            name {
                value
            }
            address {
                node {
                    address {
                        value
                    }
                }
                properties {
                    source {
                        id
                    }
                }
            }
        }
    }
}
"""

PREFIX_MUTATION = """
mutation CreatePrefix($name: String!, $pool: String!, $identifier: String){
    TestMandatoryPrefixCreate(data: {
        name: { value: $name }
        prefix: {
            from_pool: {
                id: $pool
                identifier: $identifier
            }
        }
    }) {
        ok
        object {
            name {
                value
            }
            prefix {
                node {
                    prefix {
                        value
                    }
                }
                properties {
                    source {
                        id
                    }
                }
            }
        }
    }
}
"""

ALLOCATED = """
query Allocated($pool_id: String!, $resource_id: String!) {
  InfrahubResourcePoolAllocated(pool_id: $pool_id, resource_id: $resource_id) {
    count
    edges {
      node {
        branch
        display_label
        id
        identifier
        kind
      }
    }
  }
}
"""


async def test_create_ipv6_prefix_and_read_allocations(db: InfrahubDatabase, default_branch: Branch, prefix_pools_02):
    ipv6_prefix_resource = prefix_pools_02["ipv6_prefix_resource"]
    ipv6_prefix_pool = prefix_pools_02["ipv6_prefix_pool"]

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    site1_result = await graphql(
        schema=gql_params.schema,
        source=PREFIX_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "site1", "pool": ipv6_prefix_pool.id, "identifier": "site1"},
    )

    site2_result = await graphql(
        schema=gql_params.schema,
        source=PREFIX_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "site2", "pool": ipv6_prefix_pool.id, "identifier": "site2"},
    )

    site3_result = await graphql(
        schema=gql_params.schema,
        source=PREFIX_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "name": "site3",
            "pool": ipv6_prefix_pool.id,
        },
    )

    assert not site1_result.errors
    assert site1_result.data
    assert site1_result.data["TestMandatoryPrefixCreate"]["ok"]
    site1_prefix = site1_result.data["TestMandatoryPrefixCreate"]["object"]["prefix"]["node"]["prefix"]["value"]

    assert not site2_result.errors
    assert site2_result.data
    assert site2_result.data["TestMandatoryPrefixCreate"]["ok"]
    site2_prefix = site2_result.data["TestMandatoryPrefixCreate"]["object"]["prefix"]["node"]["prefix"]["value"]

    assert not site3_result.errors
    assert site3_result.data
    assert site3_result.data["TestMandatoryPrefixCreate"]["ok"]
    site3_prefix = site3_result.data["TestMandatoryPrefixCreate"]["object"]["prefix"]["node"]["prefix"]["value"]

    allocated_result = await graphql(
        schema=gql_params.schema,
        source=ALLOCATED,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "pool_id": ipv6_prefix_pool.id,
            "resource_id": ipv6_prefix_resource.id,
        },
    )

    assert not allocated_result.errors
    assert allocated_result.data
    # The count is the three allocated within this test along and one created in the fixture
    assert allocated_result.data["InfrahubResourcePoolAllocated"]["count"] == 4

    nodes = allocated_result.data["InfrahubResourcePoolAllocated"]["edges"]

    prefixes = [node["node"]["display_label"] for node in nodes]
    assert site1_prefix in prefixes
    assert site2_prefix in prefixes
    assert site3_prefix in prefixes


async def test_create_ipv4_prefix_and_read_allocations(db: InfrahubDatabase, default_branch: Branch, prefix_pools_02):
    ipv4_prefix_resource = prefix_pools_02["ipv4_prefix_resource"]
    ipv4_prefix_pool = prefix_pools_02["ipv4_prefix_pool"]

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    site1_result = await graphql(
        schema=gql_params.schema,
        source=PREFIX_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "site1", "pool": ipv4_prefix_pool.id, "identifier": "site1"},
    )

    site2_result = await graphql(
        schema=gql_params.schema,
        source=PREFIX_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "site2", "pool": ipv4_prefix_pool.id, "identifier": "site2"},
    )

    site3_result = await graphql(
        schema=gql_params.schema,
        source=PREFIX_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "name": "site3",
            "pool": ipv4_prefix_pool.id,
        },
    )

    assert not site1_result.errors
    assert site1_result.data
    assert site1_result.data["TestMandatoryPrefixCreate"]["ok"]
    site1_prefix = site1_result.data["TestMandatoryPrefixCreate"]["object"]["prefix"]["node"]["prefix"]["value"]

    assert not site2_result.errors
    assert site2_result.data
    assert site2_result.data["TestMandatoryPrefixCreate"]["ok"]
    site2_prefix = site2_result.data["TestMandatoryPrefixCreate"]["object"]["prefix"]["node"]["prefix"]["value"]

    assert not site3_result.errors
    assert site3_result.data
    assert site3_result.data["TestMandatoryPrefixCreate"]["ok"]
    site3_prefix = site3_result.data["TestMandatoryPrefixCreate"]["object"]["prefix"]["node"]["prefix"]["value"]

    allocated_result = await graphql(
        schema=gql_params.schema,
        source=ALLOCATED,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "pool_id": ipv4_prefix_pool.id,
            "resource_id": ipv4_prefix_resource.id,
        },
    )

    assert not allocated_result.errors
    assert allocated_result.data
    assert allocated_result.data["InfrahubResourcePoolAllocated"]["count"] == 3

    nodes = allocated_result.data["InfrahubResourcePoolAllocated"]["edges"]

    prefixes = [node["node"]["display_label"] for node in nodes]
    assert site1_prefix in prefixes
    assert site2_prefix in prefixes
    assert site3_prefix in prefixes


async def test_create_ipv4_address_and_read_allocations(db: InfrahubDatabase, default_branch: Branch, prefix_pools_02):
    ipv4_address_resource = prefix_pools_02["ipv4_address_resource"]
    ipv4_address_pool = prefix_pools_02["ipv4_address_pool"]

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    device1_result = await graphql(
        schema=gql_params.schema,
        source=ADDRESS_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "device1", "pool": ipv4_address_pool.id, "identifier": "site1"},
    )

    device2_result = await graphql(
        schema=gql_params.schema,
        source=ADDRESS_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "device1", "pool": ipv4_address_pool.id, "identifier": "site2"},
    )

    device3_result = await graphql(
        schema=gql_params.schema,
        source=ADDRESS_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "device3", "pool": ipv4_address_pool.id, "identifier": "site3"},
    )

    assert not device1_result.errors
    assert device1_result.data
    assert device1_result.data["TestMandatoryAddressCreate"]["ok"]
    device1_address = device1_result.data["TestMandatoryAddressCreate"]["object"]["address"]["node"]["address"]["value"]

    assert not device2_result.errors
    assert device2_result.data
    assert device2_result.data["TestMandatoryAddressCreate"]["ok"]
    device2_address = device2_result.data["TestMandatoryAddressCreate"]["object"]["address"]["node"]["address"]["value"]

    assert not device3_result.errors
    assert device3_result.data
    assert device3_result.data["TestMandatoryAddressCreate"]["ok"]
    device3_address = device3_result.data["TestMandatoryAddressCreate"]["object"]["address"]["node"]["address"]["value"]

    allocated_result = await graphql(
        schema=gql_params.schema,
        source=ALLOCATED,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "pool_id": ipv4_address_pool.id,
            "resource_id": ipv4_address_resource.id,
        },
    )

    assert not allocated_result.errors
    assert allocated_result.data
    assert allocated_result.data["InfrahubResourcePoolAllocated"]["count"] == 3

    nodes = allocated_result.data["InfrahubResourcePoolAllocated"]["edges"]

    addresses = [node["node"]["display_label"] for node in nodes]
    assert device1_address in addresses
    assert device2_address in addresses
    assert device3_address in addresses
