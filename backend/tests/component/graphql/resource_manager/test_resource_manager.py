from typing import Any

import pytest

from infrahub.auth.session import AccountSession
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.events.node_action import NodeCreatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.graphql import graphql
from tests.helpers.schema import TICKET, load_schema

FAKE_POOL_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
FAKE_POOL_NAME = "nonexistent-pool"

CREATE_PREFIX_FROM_POOL = """
mutation CreatePrefixFromPool($name: String!, $pool_id: String!) {
    TestMandatoryPrefixCreate(data: {
        name: { value: $name }
        prefix: {
            from_pool: {
                id: $pool_id
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

CREATE_ADDRESS_FROM_POOL = """
mutation CreateAddressFromPool($name: String!, $pool_id: String!) {
    TestMandatoryAddressCreate(data: {
        name: { value: $name }
        address: {
            from_pool: {
                id: $pool_id
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

CREATE_TICKET_WITH_POOL = """
mutation CreateTicketWithPool($pool_id: String!) {
    TestingTicketCreate(data: {
        title: { value: "ticket-bad-pool" }
        ticket_id: {
            from_pool: {
                id: $pool_id
            }
        }
    }) {
        ok
    }
}
"""

CREATE_TEMPLATE_TICKET_WITH_POOL = """
mutation CreateTemplateTicketWithPool($pool_id: String!) {
    TemplateTestingTicketCreate(data: {
        template_name: { value: "bad-pool-template" }
        ticket_id_from_resource_pool: { id: $pool_id }
    }) {
        ok
    }
}
"""

UPDATE_TICKET_WITH_POOL = """
mutation UpdateTicketWithPool($ticket_id: String!, $pool_id: String!) {
    TestingTicketUpdate(data: {
        id: $ticket_id
        ticket_id: {
            from_pool: {
                id: $pool_id
            }
        }
    }) {
        ok
    }
}
"""

UPDATE_PREFIX_FROM_POOL = """
mutation UpdatePrefixFromPool($id: String!, $pool_id: String!) {
    TestMandatoryPrefixUpdate(data: {
        id: $id
        prefix: {
            from_pool: {
                id: $pool_id
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

PREFIX_POOL_GET_RESOURCE = """
mutation PrefixPoolGetResource($pool_id: String!) {
    InfrahubIPPrefixPoolGetResource(data: {
        id: $pool_id
    }) {
        ok
        node {
            kind
            display_label
        }
    }
}
"""

PREFIX_POOL_GET_RESOURCE_WITH_IDENTIFIER = """
mutation PrefixPoolGetResourceWithIdentifier($pool_id: String!, $identifier: String!) {
    InfrahubIPPrefixPoolGetResource(data: {
        id: $pool_id
        identifier: $identifier
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

PREFIX_POOL_GET_RESOURCE_WITH_PREFIX_LENGTH = """
mutation PrefixPoolGetResourceWithPrefixLength($pool_id: String!, $prefix_length: Int!) {
    InfrahubIPPrefixPoolGetResource(data: {
        id: $pool_id
        prefix_length: $prefix_length
    }) {
        ok
        node {
            kind
            display_label
        }
    }
}
"""

ADDRESS_POOL_GET_RESOURCE = """
mutation AddressPoolGetResource($pool_id: String!) {
    InfrahubIPAddressPoolGetResource(data: {
        id: $pool_id
    }) {
        ok
        node {
            kind
            display_label
        }
    }
}
"""

ADDRESS_POOL_GET_RESOURCE_WITH_IDENTIFIER = """
mutation AddressPoolGetResourceWithIdentifier($pool_id: String!, $identifier: String!) {
    InfrahubIPAddressPoolGetResource(data: {
        id: $pool_id
        identifier: $identifier
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

ADDRESS_POOL_GET_RESOURCE_WITH_PREFIX_LENGTH = """
mutation AddressPoolGetResourceWithPrefixLength($pool_id: String!, $prefix_length: Int!) {
    InfrahubIPAddressPoolGetResource(data: {
        id: $pool_id
        prefix_length: $prefix_length
    }) {
        ok
        node {
            kind
            display_label
        }
    }
}
"""


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

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_PREFIX_FROM_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "site1", "pool_id": pool.id},
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


@pytest.mark.parametrize(
    "query,field,name",
    [
        pytest.param(CREATE_PREFIX_FROM_POOL, "prefix", "site-bad-pool", id="prefix"),
        pytest.param(CREATE_ADDRESS_FROM_POOL, "address", "server-bad-pool", id="address"),
    ],
)
async def test_create_object_with_invalid_ip_pool_id(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry: None,
    query: str,
    field: str,
    name: str,
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": name, "pool_id": FAKE_POOL_ID},
    )

    assert result.errors
    assert f"Unable to find the pool to generate a node for the relationship '{field}'" in str(result.errors[0])


async def test_create_object_with_invalid_number_pool_id(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    default_branch.update_schema_hash()

    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_TICKET_WITH_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": FAKE_POOL_ID},
    )

    assert result.errors
    assert f"The pool requested {{'id': '{FAKE_POOL_ID}'}} was not found." in str(result.errors[0])


async def test_create_template_with_invalid_number_pool_id(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Creating a template with from_pool referencing a nonexistent number pool should fail."""
    ticket_with_template = TICKET.model_copy(deep=True)
    ticket_with_template.generate_template = True
    ticket_with_template.get_attribute(name="ticket_id").unique = False
    await load_schema(db=db, schema=SchemaRoot(nodes=[ticket_with_template]))
    default_branch.update_schema_hash()

    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_TEMPLATE_TICKET_WITH_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": FAKE_POOL_ID},
    )

    assert result.errors
    assert f"Unable to find the node {FAKE_POOL_ID} / CoreNumberPool in the database." in str(result.errors[0])


async def test_update_object_with_invalid_number_pool_id(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Updating an existing node's Number attribute with from_pool referencing a nonexistent pool should fail."""
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    default_branch.update_schema_hash()

    schema = registry.schema.get_node_schema(name="TestingTicket", branch=default_branch)
    ticket = await Node.init(db=db, schema=schema, branch=default_branch)
    await ticket.new(db=db, title="existing-ticket", ticket_id=42)
    await ticket.save(db=db)

    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_TICKET_WITH_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"ticket_id": ticket.id, "pool_id": FAKE_POOL_ID},
    )

    assert result.errors
    assert f"The pool requested {{'id': '{FAKE_POOL_ID}'}} was not found." in str(result.errors[0])


async def test_update_object_and_assign_prefix_from_pool(
    db: InfrahubDatabase, default_branch: Branch, prefix_pool_01: Node
) -> None:
    pool = prefix_pool_01["pool"]
    net142 = prefix_pool_01["net142"]

    schema = registry.schema.get_node_schema(name="TestMandatoryPrefix", branch=default_branch)

    obj = await Node.init(db=db, schema=schema, branch=default_branch)
    await obj.new(db=db, name="site1", prefix=net142)
    await obj.save(db=db)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_PREFIX_FROM_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": obj.id, "pool_id": pool.id},
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

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_ADDRESS_FROM_POOL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "server1", "pool_id": pool.id},
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

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=PREFIX_POOL_GET_RESOURCE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": pool.id},
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

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)
    result = await graphql(
        schema=gql_params.schema,
        source=PREFIX_POOL_GET_RESOURCE_WITH_IDENTIFIER,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": pool.id, "identifier": "myidentifier"},
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

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=PREFIX_POOL_GET_RESOURCE_WITH_PREFIX_LENGTH,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": pool.id, "prefix_length": 31},
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

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=ADDRESS_POOL_GET_RESOURCE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": pool.id},
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

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=ADDRESS_POOL_GET_RESOURCE_WITH_IDENTIFIER,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": pool.id, "identifier": "myidentifier"},
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

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=ADDRESS_POOL_GET_RESOURCE_WITH_PREFIX_LENGTH,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": pool.id, "prefix_length": 32},
    )

    assert not result.errors
    assert result.data
    assert result.data["InfrahubIPAddressPoolGetResource"]["ok"]
    assert result.data["InfrahubIPAddressPoolGetResource"]["node"] == {
        "display_label": "10.10.3.2/32",
        "kind": "IpamIPAddress",
    }
