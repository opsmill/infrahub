import pytest
from graphql import graphql

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch, initialization
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.schema import TICKET, load_schema


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
        default_prefix_length=56,
        default_prefix_type="IpamIPPrefix",
        resources=[ipv6_prefix_resource],
        ip_namespace=ns1,
    )
    await ipv6_prefix_pool.save(db=db)

    ipv4_prefix_pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db, branch=default_branch)
    await ipv4_prefix_pool.new(
        db=db,
        name="ipv4_prefix",
        default_prefix_length=26,
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
        "ns1": ns1,
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

RESOURCES = """
query Resources($pool_ids: [ID]) {
  CoreIPAddressPool(ids: $pool_ids) {
    count
    edges {
      node {
        id
        resources {
          count
          edges {
            node {
              id
            }
          }
        }
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


async def test_read_resources_in_pool_with_branch(db: InfrahubDatabase, default_branch: Branch, prefix_pools_02):
    ns1 = prefix_pools_02["ns1"]
    ipv4_address_pool = prefix_pools_02["ipv4_address_pool"]
    peers = await ipv4_address_pool.resources.get_peers(db=db)

    # At first there should be 1 resource
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    resources_result = await graphql(
        schema=gql_params.schema,
        source=RESOURCES,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": ipv4_address_pool.id},
    )

    assert not resources_result.errors
    assert resources_result.data
    assert resources_result.data["CoreIPAddressPool"]["edges"][0]["node"]["resources"]["count"] == 1

    # Create a branch
    branch = await create_branch(branch_name="issue-3579", db=db)

    # Create a prefix and add it to resource pool in branch
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=branch)
    rfc5735 = await Node.init(db=db, schema=prefix_schema, branch=branch)
    await rfc5735.new(db=db, prefix="192.0.2.0/24", ip_namespace=ns1)
    await rfc5735.save(db=db)

    # Resource manager in the branch
    branched_ipv4_address_pool = await NodeManager.get_one(db=db, id=ipv4_address_pool.id, branch=branch)
    await branched_ipv4_address_pool.resources.update(db=db, data=list(peers.values()) + [rfc5735])
    await branched_ipv4_address_pool.save(db=db)
    branched_peers = await branched_ipv4_address_pool.resources.get_peers(db=db)
    branched_peer_ids = [peer.id for peer in branched_peers.values()]

    # In main there should be 1 resource
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    resources_result = await graphql(
        schema=gql_params.schema,
        source=RESOURCES,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_ids": [ipv4_address_pool.id]},
    )

    assert not resources_result.errors
    assert resources_result.data
    assert resources_result.data["CoreIPAddressPool"]["count"] == 1
    assert resources_result.data["CoreIPAddressPool"]["edges"][0]["node"]["resources"]["count"] == 2
    assert {
        edge["node"]["id"]
        for edge in resources_result.data["CoreIPAddressPool"]["edges"][0]["node"]["resources"]["edges"]
    } == set(branched_peer_ids)

    # In branch there should be 2 resources
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch.name)
    resources_result = await graphql(
        schema=gql_params.schema,
        source=RESOURCES,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_ids": [branched_ipv4_address_pool.id]},
    )

    assert not resources_result.errors
    assert resources_result.data
    assert resources_result.data["CoreIPAddressPool"]["count"] == 1
    assert resources_result.data["CoreIPAddressPool"]["edges"][0]["node"]["resources"]["count"] == 2
    assert {
        edge["node"]["id"]
        for edge in resources_result.data["CoreIPAddressPool"]["edges"][0]["node"]["resources"]["edges"]
    } == set(branched_peer_ids)


async def test_read_resources_in_pool_with_branch_with_mutations(
    db: InfrahubDatabase, default_branch: Branch, prefix_pools_02
):
    ns1 = prefix_pools_02["ns1"]
    ipv4_address_pool = prefix_pools_02["ipv4_address_pool"]
    peers = await ipv4_address_pool.resources.get_peers(db=db)
    peer_ids = [peer.id for peer in peers.values()]
    assert len(peer_ids) == 1
    peer_id = peer_ids[0]

    # At first there should be 1 resource
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    resources_result = await graphql(
        schema=gql_params.schema,
        source=RESOURCES,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": ipv4_address_pool.id},
    )

    assert not resources_result.errors
    assert resources_result.data
    assert resources_result.data["CoreIPAddressPool"]["edges"][0]["node"]["resources"]["count"] == 1

    # Create a branch
    branch = await create_branch(branch_name="issue-3579", db=db)

    # Create a prefix
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    prefix_result = await graphql(
        schema=gql_params.schema,
        source="""
        mutation {
            IpamIPPrefixCreate(data: {prefix: {value: "192.0.2.0/24"}, ip_namespace: {id: "%s"}}) {
                ok
                object {
                    id
                }
            }
        }
        """
        % ns1.id,
        context_value=gql_params.context,
        root_value=None,
    )
    prefix_id = prefix_result.data["IpamIPPrefixCreate"]["object"]["id"]

    # Add it to resource pool in branch
    await graphql(
        schema=gql_params.schema,
        source="""
        mutation {
            CoreIPAddressPoolUpdate(data: {
                id: "%s", resources: [{id: "%s"}, {id: "%s"}]
            }) {
                ok
            }
        }
        """
        % (ipv4_address_pool.id, peer_id, prefix_id),
        context_value=gql_params.context,
        root_value=None,
    )

    # In main there should be 1 resource
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    resources_result = await graphql(
        schema=gql_params.schema,
        source=RESOURCES,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_ids": [ipv4_address_pool.id]},
    )

    assert not resources_result.errors
    assert resources_result.data
    assert resources_result.data["CoreIPAddressPool"]["count"] == 1
    assert resources_result.data["CoreIPAddressPool"]["edges"][0]["node"]["resources"]["count"] == 2
    assert {
        edge["node"]["id"]
        for edge in resources_result.data["CoreIPAddressPool"]["edges"][0]["node"]["resources"]["edges"]
    } == {peer_id, prefix_id}

    # In branch there should be 2 resources
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch.name)
    resources_result = await graphql(
        schema=gql_params.schema,
        source=RESOURCES,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_ids": [ipv4_address_pool.id]},
    )

    assert not resources_result.errors
    assert resources_result.data
    assert resources_result.data["CoreIPAddressPool"]["count"] == 1
    assert resources_result.data["CoreIPAddressPool"]["edges"][0]["node"]["resources"]["count"] == 2
    assert {
        edge["node"]["id"]
        for edge in resources_result.data["CoreIPAddressPool"]["edges"][0]["node"]["resources"]["edges"]
    } == {peer_id, prefix_id}


async def test_number_pool_utilization(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema):
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    await initialization(db=db)
    create_ok = await graphql(
        schema=gql_params.schema,
        source=CREATE_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "name": "pool1",
            "node": "TestingTicket",
            "node_attribute": "ticket_id",
            "start_range": 1,
            "end_range": 10,
        },
    )

    assert create_ok.data
    assert not create_ok.errors

    pool_id = create_ok.data["CoreNumberPoolCreate"]["object"]["id"]

    first = await graphql(
        schema=gql_params.schema,
        source=CREATE_TICKET,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "title": "first",
            "pool": pool_id,
        },
    )

    second = await graphql(
        schema=gql_params.schema,
        source=CREATE_TICKET,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "title": "second",
            "pool": pool_id,
        },
    )

    third = await graphql(
        schema=gql_params.schema,
        source=CREATE_TICKET,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "title": "second",
            "pool": pool_id,
        },
    )

    assert not first.errors
    assert not second.errors
    assert not third.errors

    assert first.data
    assert second.data
    assert third.data
    second_id = second.data["TestingTicketCreate"]["object"]["id"]

    utilization = await graphql(
        schema=gql_params.schema,
        source=POOL_UTILIZATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "pool_id": pool_id,
        },
    )

    assert not utilization.errors
    assert utilization.data

    # Number pools tied to an attribute always has a count of 1
    assert utilization.data["InfrahubResourcePoolUtilization"]["count"] == 1
    assert utilization.data["InfrahubResourcePoolUtilization"]["utilization"] == 30.0
    assert utilization.data["InfrahubResourcePoolUtilization"]["edges"][0]["node"]["display_label"] == "pool1"
    assert utilization.data["InfrahubResourcePoolUtilization"]["edges"][0]["node"]["utilization"] == 30.0

    allocation = await graphql(
        schema=gql_params.schema,
        source=POOL_ALLOCATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "pool_id": pool_id,
            "resource_id": pool_id,
        },
    )

    assert not allocation.errors
    assert allocation.data
    assert allocation.data["InfrahubResourcePoolAllocated"]["count"] == 3
    numbers = [entry["node"]["display_label"] for entry in allocation.data["InfrahubResourcePoolAllocated"]["edges"]]
    assert sorted(numbers) == ["1", "2", "3"]

    remove_two = await graphql(
        schema=gql_params.schema,
        source=DELETE_TICKET,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": second_id},
    )
    assert not remove_two.errors

    allocation = await graphql(
        schema=gql_params.schema,
        source=POOL_ALLOCATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "pool_id": pool_id,
            "resource_id": pool_id,
        },
    )

    assert not allocation.errors
    assert allocation.data
    assert allocation.data["InfrahubResourcePoolAllocated"]["count"] == 2
    numbers = [entry["node"]["display_label"] for entry in allocation.data["InfrahubResourcePoolAllocated"]["edges"]]
    assert sorted(numbers) == ["1", "3"]


CREATE_NUMBER_POOL = """
mutation CreateNumberPool(
    $name: String!,
    $node: String!,
    $node_attribute: String!,
    $start_range: BigInt!,
    $end_range: BigInt!
  ) {
  CoreNumberPoolCreate(
    data: {
      name: {value: $name},
      node:{value: $node},
      node_attribute: {value: $node_attribute},
      start_range: {value: $start_range},
      end_range: {value: $end_range}
    }
  ) {
    object {
      display_label
      id
    }
  }
}
"""


CREATE_TICKET = """
mutation CreateTestingTicket(
    $pool: String!,
    $title: String!
	) {
  TestingTicketCreate(
    data: {
        ticket_id: {
            from_pool: {
                id: $pool
            }
        },
        title: {value: $title}
      }) {
    object {
      id
      title { value }
      ticket_id { value }
    }
  }
}
"""

DELETE_TICKET = """
mutation DeleteTicket($id: String!) {
  TestingTicketDelete(data: {id: $id}) {
    ok
  }
}
"""

POOL_UTILIZATION = """
query PoolUtilization($pool_id: String!) {
  InfrahubResourcePoolUtilization(pool_id: $pool_id) {
    count
    edges {
      node {
        display_label
        id
        kind
        utilization
        utilization_branches
        utilization_default_branch
        weight
      }
    }
    utilization
    utilization_branches
    utilization_default_branch
  }
}
"""

POOL_ALLOCATION = """
query PoolUtilization($pool_id: String!, $resource_id: String!) {
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
