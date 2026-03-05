import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql
from tests.helpers.schema import TICKET, load_schema

FAKE_POOL_NAME = "nonexistent-pool"
TICKET_POOL_NAME = "ticket-pool-by-name"

CREATE_TICKET_WITH_POOL = """
mutation CreateTicketWithPool($pool_id: String!) {
    TestingTicketCreate(data: {
        title: { value: "ticket-from-pool" }
        ticket_id: {
            from_pool: {
                id: $pool_id
            }
        }
    }) {
        ok
        object {
            id
        }
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


class TestNumberPoolLookupByName:
    """Tests for referencing number pools by name instead of UUID in from_pool."""

    @pytest.fixture(scope="class")
    async def number_pool(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> CoreNumberPool:
        await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
        registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool

        pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
        await pool.new(
            db=db,
            name=TICKET_POOL_NAME,
            node="TestingTicket",
            node_attribute="ticket_id",
            start_range=1,
            end_range=100,
        )
        await pool.save(db=db)
        default_branch_scope_class.update_schema_hash()
        return pool

    async def test_create_ticket_from_pool_by_name(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, number_pool: CoreNumberPool
    ) -> None:
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TICKET_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"pool_id": TICKET_POOL_NAME},
        )

        assert not result.errors
        assert result.data
        assert result.data["TestingTicketCreate"]["ok"]

        obj_id = result.data["TestingTicketCreate"]["object"]["id"]
        loaded = await NodeManager.get_one(
            id=obj_id, db=db, branch=default_branch_scope_class, include_metadata=MetadataOptions.LINKED_NODES
        )
        assert loaded is not None
        assert loaded.ticket_id.source_id == number_pool.id

    async def test_update_ticket_from_pool_by_name(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, number_pool: CoreNumberPool
    ) -> None:
        schema = registry.schema.get_node_schema(name="TestingTicket", branch=default_branch_scope_class)
        ticket = await Node.init(db=db, schema=schema, branch=default_branch_scope_class)
        await ticket.new(db=db, title="ticket-for-update-by-name", ticket_id=42)
        await ticket.save(db=db)

        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TICKET_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"ticket_id": ticket.id, "pool_id": TICKET_POOL_NAME},
        )

        assert not result.errors
        assert result.data
        assert result.data["TestingTicketUpdate"]["ok"]

        loaded = await NodeManager.get_one(
            id=ticket.id, db=db, branch=default_branch_scope_class, include_metadata=MetadataOptions.LINKED_NODES
        )
        assert loaded is not None
        assert loaded.ticket_id.source_id == number_pool.id

    async def test_create_ticket_with_invalid_pool_name(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, number_pool: CoreNumberPool
    ) -> None:
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TICKET_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"pool_id": FAKE_POOL_NAME},
        )

        assert result.errors
        assert f"The pool requested {{'id': '{FAKE_POOL_NAME}'}} was not found." in str(result.errors[0])

    async def test_update_ticket_with_invalid_pool_name(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, number_pool: CoreNumberPool
    ) -> None:
        schema = registry.schema.get_node_schema(name="TestingTicket", branch=default_branch_scope_class)
        ticket = await Node.init(db=db, schema=schema, branch=default_branch_scope_class)
        await ticket.new(db=db, title="ticket-for-bad-update", ticket_id=99)
        await ticket.save(db=db)

        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TICKET_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"ticket_id": ticket.id, "pool_id": FAKE_POOL_NAME},
        )

        assert result.errors
        assert f"The pool requested {{'id': '{FAKE_POOL_NAME}'}} was not found." in str(result.errors[0])
