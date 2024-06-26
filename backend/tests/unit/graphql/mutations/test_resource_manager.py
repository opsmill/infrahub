import pytest
from graphql import graphql

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema_manager import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params
from tests.helpers.schema import TICKET, load_schema


@pytest.fixture
async def prefix_pool_01(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry,
    ip_dataset_prefix_v4,
):
    ns1 = ip_dataset_prefix_v4["ns1"]
    net140 = ip_dataset_prefix_v4["net140"]

    prefix_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)

    pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db, branch=default_branch)
    await pool.new(
        db=db,
        name="pool1",
        default_prefix_length=24,
        default_prefix_type="IpamIPPrefix",
        resources=[net140],
        ip_namespace=ns1,
    )
    await pool.save(db=db)

    ip_dataset_prefix_v4["pool"] = pool

    return ip_dataset_prefix_v4


async def test_create_object_and_assign_prefix_from_pool(db: InfrahubDatabase, default_branch: Branch, prefix_pool_01):
    pool = prefix_pool_01["pool"]

    query = (
        """
    mutation {
        TestMandatoryPrefixCreate(data: {
            name: { value: "site1" }
            prefix: {
                from_pool: {
                    id: "%s"
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
        % pool.id
    )

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert result.data
    assert result.data["TestMandatoryPrefixCreate"]["ok"]
    assert result.data["TestMandatoryPrefixCreate"]["object"] == {
        "name": {"value": "site1"},
        "prefix": {
            "node": {"prefix": {"value": "10.10.0.0/24"}},
            "properties": {
                "source": {"id": pool.id},
            },
        },
    }


async def test_update_object_and_assign_prefix_from_pool(db: InfrahubDatabase, default_branch: Branch, prefix_pool_01):
    pool = prefix_pool_01["pool"]
    net142 = prefix_pool_01["net142"]

    schema = registry.schema.get_node_schema(name="TestMandatoryPrefix", branch=default_branch)

    obj = await Node.init(db=db, schema=schema, branch=default_branch)
    await obj.new(db=db, name="site1", prefix=net142)
    await obj.save(db=db)

    query = """
    mutation {
        TestMandatoryPrefixUpdate(data: {
            id: "%s"
            prefix: {
                from_pool: {
                    id: "%s"
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
    """ % (obj.id, pool.id)

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert result.data
    assert result.data["TestMandatoryPrefixUpdate"]["ok"]
    assert result.data["TestMandatoryPrefixUpdate"]["object"] == {
        "name": {"value": "site1"},
        "prefix": {
            "node": {"prefix": {"value": "10.10.0.0/24"}},
            "properties": {
                "source": {"id": pool.id},
            },
        },
    }


async def test_create_object_and_assign_address_from_pool(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry,
    ip_dataset_prefix_v4,
):
    ns1 = ip_dataset_prefix_v4["ns1"]
    net145 = ip_dataset_prefix_v4["net145"]

    address_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)

    pool = await CoreIPAddressPool.init(schema=address_pool_schema, db=db, branch=default_branch)
    await pool.new(
        db=db,
        name="pool1",
        default_address_type="IpamIPAddress",
        resources=[net145],
        ip_namespace=ns1,
    )
    await pool.save(db=db)

    query = (
        """
    mutation {
        TestMandatoryAddressCreate(data: {
            name: { value: "server1" }
            address: {
                from_pool: {
                    id: "%s"
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
        % pool.id
    )

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert result.data
    assert result.data["TestMandatoryAddressCreate"]["ok"]
    assert result.data["TestMandatoryAddressCreate"]["object"] == {
        "name": {"value": "server1"},
        "address": {
            "node": {"address": {"value": "10.10.3.2/27"}},
            "properties": {
                "source": {"id": pool.id},
            },
        },
    }


async def test_prefix_pool_get_resource(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry,
    ip_dataset_prefix_v4,
):
    ns1 = ip_dataset_prefix_v4["ns1"]
    net140 = ip_dataset_prefix_v4["net140"]

    prefix_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)

    pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db, branch=default_branch)
    await pool.new(
        db=db,
        name="pool1",
        default_prefix_length=24,
        default_prefix_type="IpamIPPrefix",
        resources=[net140],
        ip_namespace=ns1,
    )
    await pool.save(db=db)

    query = (
        """
    mutation {
        IPPrefixPoolGetResource(data: {
            id: "%s"
        }) {
            ok
            node {
                kind
                display_label
            }
        }
    }
    """
        % pool.id
    )

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert result.data
    assert result.data["IPPrefixPoolGetResource"]["ok"]
    assert result.data["IPPrefixPoolGetResource"]["node"] == {
        "display_label": "10.10.0.0/24",
        "kind": "IpamIPPrefix",
    }


async def test_prefix_pool_get_resource_with_identifier(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry,
    ip_dataset_prefix_v4,
):
    ns1 = ip_dataset_prefix_v4["ns1"]
    net140 = ip_dataset_prefix_v4["net140"]

    prefix_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)

    pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db, branch=default_branch)
    await pool.new(
        db=db,
        name="pool1",
        default_prefix_length=24,
        default_prefix_type="IpamIPPrefix",
        resources=[net140],
        ip_namespace=ns1,
    )
    await pool.save(db=db)

    resource = await pool.get_resource(db=db, identifier="myidentifier", branch=default_branch)

    query = (
        """
    mutation {
        IPPrefixPoolGetResource(data: {
            id: "%s"
            identifier: "myidentifier"
        }) {
            ok
            node {
                id
                kind
                display_label
                identifier
            }
        }
    }
    """
        % pool.id
    )

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert result.data
    assert result.data["IPPrefixPoolGetResource"]["ok"]
    assert result.data["IPPrefixPoolGetResource"]["node"] == {
        "id": resource.id,
        "display_label": "10.10.0.0/24",
        "kind": "IpamIPPrefix",
        "identifier": "myidentifier",
    }


async def test_prefix_pool_get_resource_with_prefix_length(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry,
    ip_dataset_prefix_v4,
):
    ns1 = ip_dataset_prefix_v4["ns1"]
    net140 = ip_dataset_prefix_v4["net140"]

    prefix_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)

    pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db, branch=default_branch)
    await pool.new(
        db=db,
        name="pool1",
        default_prefix_length=24,
        default_prefix_type="IpamIPPrefix",
        resources=[net140],
        ip_namespace=ns1,
    )
    await pool.save(db=db)

    query = (
        """
    mutation {
        IPPrefixPoolGetResource(data: {
            id: "%s"
            prefix_length: 31
        }) {
            ok
            node {
                kind
                display_label
            }
        }
    }
    """
        % pool.id
    )

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert result.data
    assert result.data["IPPrefixPoolGetResource"]["ok"]
    assert result.data["IPPrefixPoolGetResource"]["node"] == {"display_label": "10.10.3.32/31", "kind": "IpamIPPrefix"}


async def test_address_pool_get_resource(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry,
    ip_dataset_prefix_v4,
):
    ns1 = ip_dataset_prefix_v4["ns1"]
    net145 = ip_dataset_prefix_v4["net145"]

    address_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)

    pool = await CoreIPAddressPool.init(schema=address_pool_schema, db=db, branch=default_branch)
    await pool.new(
        db=db,
        name="pool1",
        default_address_type="IpamIPAddress",
        resources=[net145],
        ip_namespace=ns1,
    )
    await pool.save(db=db)

    query = (
        """
    mutation {
        IPAddressPoolGetResource(data: {
            id: "%s"
        }) {
            ok
            node {
                kind
                display_label
            }
        }
    }
    """
        % pool.id
    )

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert result.data
    assert result.data["IPAddressPoolGetResource"]["ok"]
    assert result.data["IPAddressPoolGetResource"]["node"] == {"display_label": "10.10.3.2/27", "kind": "IpamIPAddress"}


async def test_address_pool_get_resource_with_identifier(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry,
    ip_dataset_prefix_v4,
):
    ns1 = ip_dataset_prefix_v4["ns1"]
    net145 = ip_dataset_prefix_v4["net145"]

    address_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)

    pool = await CoreIPAddressPool.init(schema=address_pool_schema, db=db, branch=default_branch)
    await pool.new(
        db=db,
        name="pool1",
        default_address_type="IpamIPAddress",
        resources=[net145],
        ip_namespace=ns1,
    )
    await pool.save(db=db)

    resource = await pool.get_resource(db=db, identifier="myidentifier", branch=default_branch)

    query = (
        """
    mutation {
        IPAddressPoolGetResource(data: {
            id: "%s"
            identifier: "myidentifier"
        }) {
            ok
            node {
                id
                kind
                display_label
                identifier
            }
        }
    }
    """
        % pool.id
    )

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert result.data
    assert result.data["IPAddressPoolGetResource"]["ok"]
    assert result.data["IPAddressPoolGetResource"]["node"] == {
        "id": resource.id,
        "display_label": "10.10.3.2/27",
        "kind": "IpamIPAddress",
        "identifier": "myidentifier",
    }


async def test_address_pool_get_resource_with_prefix_length(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry,
    ip_dataset_prefix_v4,
):
    ns1 = ip_dataset_prefix_v4["ns1"]
    net145 = ip_dataset_prefix_v4["net145"]

    address_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)

    pool = await CoreIPAddressPool.init(schema=address_pool_schema, db=db, branch=default_branch)
    await pool.new(
        db=db,
        name="pool1",
        default_address_type="IpamIPAddress",
        resources=[net145],
        ip_namespace=ns1,
    )
    await pool.save(db=db)

    query = (
        """
    mutation {
        IPAddressPoolGetResource(data: {
            id: "%s"
            prefix_length: 32
        }) {
            ok
            node {
                kind
                display_label
            }
        }
    }
    """
        % pool.id
    )

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert result.data
    assert result.data["IPAddressPoolGetResource"]["ok"]
    assert result.data["IPAddressPoolGetResource"]["node"] == {"display_label": "10.10.3.2/32", "kind": "IpamIPAddress"}


CREATE_NUMBER_POOL = """
mutation CreateNumberPool(
    $name: String!,
    $node: String!,
    $node_attribute: String!,
    $start_range: Int!,
    $end_range: Int!
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


async def test_test_number_pool_creation(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema):
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    no_model = await graphql(
        schema=gql_params.schema,
        source=CREATE_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "name": "pool1",
            "node": "TestNotHere",
            "node_attribute": "ticket_id",
            "start_range": 1,
            "end_range": 3,
        },
    )
    missing_attribute = await graphql(
        schema=gql_params.schema,
        source=CREATE_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "name": "pool1",
            "node": "TestingTicket",
            "node_attribute": "not_here",
            "start_range": 1,
            "end_range": 3,
        },
    )
    wrong_attribute = await graphql(
        schema=gql_params.schema,
        source=CREATE_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "name": "pool1",
            "node": "TestingTicket",
            "node_attribute": "description",
            "start_range": 1,
            "end_range": 3,
        },
    )

    assert no_model.errors
    assert "The selected model does not exist" in str(no_model.errors[0])
    assert missing_attribute.errors
    assert "The selected attribute doesn't exist in the selected" in str(missing_attribute.errors[0])
    assert wrong_attribute.errors
    assert "The selected attribute is not of the kind Number" in str(wrong_attribute.errors[0])
