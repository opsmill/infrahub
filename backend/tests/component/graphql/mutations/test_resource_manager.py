from typing import Any

import pytest

from infrahub.auth import AccountSession
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.events.node_action import NodeCreatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.manager import registry as graphql_registry
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.graphql import graphql
from tests.helpers.schema import SNOW_TICKET_SCHEMA, TICKET, load_schema


@pytest.fixture
async def prefix_pool_01(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry: None,
    ip_dataset_prefix_v4: dict[str, Any],
) -> dict[str, Any]:
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


async def test_create_object_and_assign_prefix_from_pool(
    db: InfrahubDatabase, default_branch: Branch, prefix_pool_01: Node, session_first_account: AccountSession
) -> None:
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

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert gql_params.context.background
    await gql_params.context.background()

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

    parent_events = [
        e for e in memory_event.events if isinstance(e, NodeCreatedEvent) and e.kind == "TestMandatoryPrefix"
    ]
    prefix_events = [e for e in memory_event.events if isinstance(e, NodeCreatedEvent) and e.kind == "IpamIPPrefix"]
    assert len(parent_events) == 1
    assert len(prefix_events) == 1
    assert parent_events[0].meta.account_id == session_first_account.account_id
    assert prefix_events[0].meta.account_id == session_first_account.account_id
    assert prefix_events[0].meta.parent == parent_events[0].meta.id


async def test_update_object_and_assign_prefix_from_pool(
    db: InfrahubDatabase, default_branch: Branch, prefix_pool_01: Node
) -> None:
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

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
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
    init_nodes_registry: None,
    ip_dataset_prefix_v4: dict[str, Any],
    session_first_account: AccountSession,
) -> None:
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

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert gql_params.context.background
    await gql_params.context.background()

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

    parent_events = [
        e for e in memory_event.events if isinstance(e, NodeCreatedEvent) and e.kind == "TestMandatoryAddress"
    ]
    address_events = [e for e in memory_event.events if isinstance(e, NodeCreatedEvent) and e.kind == "IpamIPAddress"]
    assert len(parent_events) == 1
    assert len(address_events) == 1
    assert parent_events[0].meta.account_id == session_first_account.account_id
    assert address_events[0].meta.account_id == session_first_account.account_id
    assert address_events[0].meta.parent == parent_events[0].meta.id


async def test_prefix_pool_get_resource(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry: None,
    ip_dataset_prefix_v4: dict[str, Any],
    session_first_account: AccountSession,
) -> None:
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
        InfrahubIPPrefixPoolGetResource(data: {
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

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert gql_params.context.background
    await gql_params.context.background()

    assert result.data
    assert result.data["InfrahubIPPrefixPoolGetResource"]["ok"]
    assert result.data["InfrahubIPPrefixPoolGetResource"]["node"] == {
        "display_label": "10.10.0.0/24",
        "kind": "IpamIPPrefix",
    }

    assert len(memory_event.events) == 2
    # The second event is related to the IP namespace
    node_event = memory_event.events[0]
    assert isinstance(node_event, NodeCreatedEvent)
    assert node_event.kind == "IpamIPPrefix"
    assert node_event.meta.account_id == session_first_account.account_id


async def test_prefix_pool_get_resource_with_identifier(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry: None,
    ip_dataset_prefix_v4: dict[str, Any],
) -> None:
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
        InfrahubIPPrefixPoolGetResource(data: {
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

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert gql_params.context.background
    await gql_params.context.background()

    assert result.data
    assert result.data["InfrahubIPPrefixPoolGetResource"]["ok"]
    assert result.data["InfrahubIPPrefixPoolGetResource"]["node"] == {
        "id": resource.id,
        "display_label": "10.10.0.0/24",
        "kind": "IpamIPPrefix",
        "identifier": "myidentifier",
    }

    # Second allocation with same identifier returns existing resource, no new CREATED event
    assert len(memory_event.events) == 0


async def test_prefix_pool_get_resource_with_prefix_length(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry: None,
    ip_dataset_prefix_v4: dict[str, Any],
) -> None:
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
        InfrahubIPPrefixPoolGetResource(data: {
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

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert result.data
    assert result.data["InfrahubIPPrefixPoolGetResource"]["ok"]
    assert result.data["InfrahubIPPrefixPoolGetResource"]["node"] == {
        "display_label": "10.10.0.0/31",
        "kind": "IpamIPPrefix",
    }


async def test_address_pool_get_resource(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry: None,
    ip_dataset_prefix_v4: dict[str, Any],
    session_first_account: AccountSession,
) -> None:
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
        InfrahubIPAddressPoolGetResource(data: {
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

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert gql_params.context.background
    await gql_params.context.background()

    assert result.data
    assert result.data["InfrahubIPAddressPoolGetResource"]["ok"]
    assert result.data["InfrahubIPAddressPoolGetResource"]["node"] == {
        "display_label": "10.10.3.2/27",
        "kind": "IpamIPAddress",
    }

    assert len(memory_event.events) == 2
    # The second event is related to the IP namespace
    node_event = memory_event.events[0]
    assert isinstance(node_event, NodeCreatedEvent)
    assert node_event.kind == "IpamIPAddress"
    assert node_event.meta.account_id == session_first_account.account_id


async def test_address_pool_get_resource_with_identifier(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry: None,
    ip_dataset_prefix_v4: dict[str, Any],
) -> None:
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
        InfrahubIPAddressPoolGetResource(data: {
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

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert result.data
    assert result.data["InfrahubIPAddressPoolGetResource"]["ok"]
    assert result.data["InfrahubIPAddressPoolGetResource"]["node"] == {
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
    init_nodes_registry: None,
    ip_dataset_prefix_v4: dict[str, Any],
) -> None:
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
        InfrahubIPAddressPoolGetResource(data: {
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

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert result.data
    assert result.data["InfrahubIPAddressPoolGetResource"]["ok"]
    assert result.data["InfrahubIPAddressPoolGetResource"]["node"] == {
        "display_label": "10.10.3.2/32",
        "kind": "IpamIPAddress",
    }


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

UPDATE_NUMBER_POOL = """
mutation UpdateNumberPool(
    $id: String!,
    $name: String,
    $node: String,
    $node_attribute: String,
    $start_range: BigInt,
    $end_range: BigInt
  ) {
  CoreNumberPoolUpdate(
    data: {
      id: $id,
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


DELETE_NUMBER_POOL = """
mutation DeleteNumberPool(
    $id: String!,
  ) {
  CoreNumberPoolDelete(
    data: {
      id: $id,
    }
  ) {
    ok
  }
}
"""


QUERY_NUMBER_POOL = """
query NumberPool(
    $id: ID!,
  ) {
  CoreNumberPool(
    ids: [$id]
  ) {
    count
  }
}
"""


async def test_test_number_pool_creation_errors(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

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
    not_a_node = await graphql(
        schema=gql_params.schema,
        source=CREATE_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "name": "pool1",
            "node": "ProfileTestingTicket",
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

    invalid_range = await graphql(
        schema=gql_params.schema,
        source=CREATE_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "name": "pool1",
            "node": "TestingTicket",
            "node_attribute": "ticket_id",
            "start_range": 10,
            "end_range": 5,
        },
    )

    assert no_model.errors
    assert "The selected model does not exist" in str(no_model.errors[0])
    assert not_a_node.errors
    assert "The selected model is not a Node" in str(not_a_node.errors[0])
    assert missing_attribute.errors
    assert "The selected attribute doesn't exist in the selected" in str(missing_attribute.errors[0])
    assert wrong_attribute.errors
    assert "The selected attribute is not of the kind Number" in str(wrong_attribute.errors[0])
    assert invalid_range.errors
    assert "start_range can't be larger than end_range" in str(invalid_range.errors[0])


async def test_test_number_pool_update(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    create_ok = await graphql(
        schema=gql_params.schema,
        source=CREATE_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "name": "pool1",
            "node": "TestingTicket",
            "node_attribute": "ticket_id",
            "start_range": 10,
            "end_range": 20,
        },
    )

    assert create_ok.data
    assert not create_ok.errors

    pool_id = create_ok.data["CoreNumberPoolCreate"]["object"]["id"]
    update_forbidden = await graphql(
        schema=gql_params.schema,
        source=UPDATE_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": pool_id,
            "node": "TestingIncident",
            "node_attribute": "ticket_id",
            "start_range": 1,
            "end_range": 10,
        },
    )

    update_invalid_range = await graphql(
        schema=gql_params.schema,
        source=UPDATE_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": pool_id,
            "start_range": 30,
        },
    )

    update_ok = await graphql(
        schema=gql_params.schema,
        source=UPDATE_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": pool_id,
            "name": "pool1b",
        },
    )

    assert update_forbidden.errors
    assert "The fields 'node' or 'node_attribute' can't be changed." in str(update_forbidden.errors[0])
    assert update_invalid_range.errors
    assert "start_range can't be larger than end_range" in str(update_invalid_range.errors[0])
    assert update_ok.data
    assert not update_ok.errors

    # Validate that we can delete a number pool that isn't tied to an attribute of kind NumberPool
    delete_ok = await graphql(
        schema=gql_params.schema,
        source=DELETE_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": pool_id,
        },
    )
    assert not delete_ok.errors
    assert delete_ok.data
    assert delete_ok.data["CoreNumberPoolDelete"]["ok"]

    query_after_delete = await graphql(
        schema=gql_params.schema,
        source=QUERY_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": pool_id,
        },
    )
    assert not query_after_delete.errors
    assert query_after_delete.data
    assert query_after_delete.data["CoreNumberPool"]["count"] == 0


@pytest.fixture
async def snow_ticket_schema_with_pools(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SNOW_TICKET_SCHEMA)
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
    snps = SchemaNumberPoolSynchronizer(db=db, schema_manager=registry.schema, upserter=upserter)
    await snps.run()
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    graphql_registry.clear_cache()


async def test_delete_number_pool_in_use_by_numberpool_attribute(
    db: InfrahubDatabase, default_branch: Branch, snow_ticket_schema_with_pools: None
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    node_schema = registry.schema.get(name="SnowTask", branch=default_branch)
    number_pool_attribute = node_schema.get_attribute(name="number")
    assert isinstance(number_pool_attribute.parameters, NumberPoolParameters)
    query_before_creation = await graphql(
        schema=gql_params.schema,
        source=QUERY_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": number_pool_attribute.parameters.number_pool_id,
        },
    )

    assert not query_before_creation.errors
    assert query_before_creation.data
    assert query_before_creation.data["CoreNumberPool"]["count"] == 1

    delete_fail = await graphql(
        schema=gql_params.schema,
        source=DELETE_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": number_pool_attribute.parameters.number_pool_id,
        },
    )

    assert delete_fail.errors
    assert "Unable to delete number pool SnowTask.number is in use (branches: main)" in str(delete_fail.errors)


async def test_update_schema_number_pool_range(
    db: InfrahubDatabase, default_branch: Branch, snow_ticket_schema_with_pools: None
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    node_schema = registry.schema.get(name="SnowTask", branch=default_branch)
    number_pool_attribute = node_schema.get_attribute(name="number")
    assert isinstance(number_pool_attribute.parameters, NumberPoolParameters)
    query_before_creation = await graphql(
        schema=gql_params.schema,
        source=QUERY_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": number_pool_attribute.parameters.number_pool_id,
        },
    )

    assert not query_before_creation.errors
    assert query_before_creation.data
    assert query_before_creation.data["CoreNumberPool"]["count"] == 1

    update_forbidden = await graphql(
        schema=gql_params.schema,
        source=UPDATE_NUMBER_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": number_pool_attribute.parameters.number_pool_id,
            "start_range": 1,
            "end_range": 10,
        },
    )

    assert update_forbidden.errors
    assert (
        "start_range or end_range can't be updated on schema defined pools, update the schema in the default branch instead"
        in str(update_forbidden.errors)
    )
