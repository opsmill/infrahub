import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql
from tests.helpers.number_pool import add_pool_range
from tests.helpers.schema import TICKET, load_schema

TEMPLATE_TICKET_POOL_NAME = "template-ticket-pool"

CREATE_TEMPLATE_TICKET_WITH_POOL = """
mutation CreateTemplateTicketWithPool($template_name: String!, $pool_id: String!) {
    TemplateTestingTicketCreate(data: {
        template_name: { value: $template_name }
        ticket_id_from_resource_pool: { id: $pool_id }
    }) {
        ok
        object {
            id
        }
    }
}
"""

CREATE_TEMPLATE_TICKET_SETUP = """
mutation CreateTemplateTicketSetup($template_name: String!) {
    TemplateTestingTicketCreate(data: {
        template_name: { value: $template_name }
    }) {
        ok
        object {
            id
        }
    }
}
"""

UPDATE_TEMPLATE_TICKET_WITH_POOL = """
mutation UpdateTemplateTicketWithPool($template_id: String!, $pool_id: String!) {
    TemplateTestingTicketUpdate(data: {
        id: $template_id
        ticket_id_from_resource_pool: { id: $pool_id }
    }) {
        ok
    }
}
"""


class TestNumberPoolTemplate:
    """Tests for creating/updating template instances with number pools by name and by ID."""

    @pytest.fixture(scope="class")
    async def number_pool(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> CoreNumberPool:
        ticket_with_template = TICKET.model_copy(deep=True)
        ticket_with_template.generate_template = True
        ticket_with_template.get_attribute(name="ticket_id").unique = False
        await load_schema(db=db, schema=SchemaRoot(nodes=[ticket_with_template]))
        registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool

        pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
        await pool.new(
            db=db,
            name=TEMPLATE_TICKET_POOL_NAME,
            node="TestingTicket",
            node_attribute="ticket_id",
            start_range=1,
            end_range=100,
        )
        await pool.save(db=db)
        await add_pool_range(db=db, pool=pool, start=1, end=100)
        default_branch_scope_class.update_schema_hash()
        return pool

    async def test_create_template_from_number_pool_by_name(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, number_pool: CoreNumberPool
    ) -> None:
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TEMPLATE_TICKET_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_name": "tpl-ticket-by-name", "pool_id": TEMPLATE_TICKET_POOL_NAME},
        )

        assert not result.errors
        assert result.data
        assert result.data["TemplateTestingTicketCreate"]["ok"]
        template_id = result.data["TemplateTestingTicketCreate"]["object"]["id"]

        loaded = await NodeManager.get_one(
            id=template_id, db=db, branch=default_branch_scope_class, include_metadata=MetadataOptions.LINKED_NODES
        )
        assert loaded is not None
        assert loaded.ticket_id.value is None
        pool_peer = await loaded.ticket_id_from_resource_pool.get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == number_pool.id

    async def test_create_template_from_number_pool_by_id(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, number_pool: CoreNumberPool
    ) -> None:
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TEMPLATE_TICKET_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_name": "tpl-ticket-by-id", "pool_id": number_pool.id},
        )

        assert not result.errors
        assert result.data
        assert result.data["TemplateTestingTicketCreate"]["ok"]
        template_id = result.data["TemplateTestingTicketCreate"]["object"]["id"]

        loaded = await NodeManager.get_one(
            id=template_id, db=db, branch=default_branch_scope_class, include_metadata=MetadataOptions.LINKED_NODES
        )
        assert loaded is not None
        assert loaded.ticket_id.value is None
        pool_peer = await loaded.ticket_id_from_resource_pool.get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == number_pool.id

    async def test_update_template_from_number_pool_by_name(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, number_pool: CoreNumberPool
    ) -> None:
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        # Create a template without pool
        create_result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TEMPLATE_TICKET_SETUP,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_name": "tpl-ticket-update-by-name"},
        )
        assert not create_result.errors
        assert create_result.data
        template_id = create_result.data["TemplateTestingTicketCreate"]["object"]["id"]

        # Update to use pool by name
        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TEMPLATE_TICKET_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_id": template_id, "pool_id": TEMPLATE_TICKET_POOL_NAME},
        )

        assert not result.errors
        assert result.data
        assert result.data["TemplateTestingTicketUpdate"]["ok"]

        loaded = await NodeManager.get_one(
            id=template_id, db=db, branch=default_branch_scope_class, include_metadata=MetadataOptions.LINKED_NODES
        )
        assert loaded is not None
        assert loaded.ticket_id.value is None
        pool_peer = await loaded.ticket_id_from_resource_pool.get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == number_pool.id

    async def test_update_template_from_number_pool_by_id(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, number_pool: CoreNumberPool
    ) -> None:
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        # Create a template without pool
        create_result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TEMPLATE_TICKET_SETUP,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_name": "tpl-ticket-update-by-id"},
        )
        assert not create_result.errors
        assert create_result.data
        template_id = create_result.data["TemplateTestingTicketCreate"]["object"]["id"]

        # Update to use pool by ID
        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TEMPLATE_TICKET_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_id": template_id, "pool_id": number_pool.id},
        )

        assert not result.errors
        assert result.data
        assert result.data["TemplateTestingTicketUpdate"]["ok"]

        loaded = await NodeManager.get_one(
            id=template_id, db=db, branch=default_branch_scope_class, include_metadata=MetadataOptions.LINKED_NODES
        )
        assert loaded is not None
        assert loaded.ticket_id.value is None
        pool_peer = await loaded.ticket_id_from_resource_pool.get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == number_pool.id
