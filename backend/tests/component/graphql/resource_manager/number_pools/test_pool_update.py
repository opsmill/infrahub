import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.mutations.resource_manager.number_pools.pool import BOUNDS_NOT_CLEARABLE
from tests.helpers.graphql import graphql
from tests.helpers.schema import TICKET, load_schema

from .helpers import CREATE_NUMBER_POOL_WITH_BOUNDS, BoundsCase

CLEARED_BOUND_CASES = [
    BoundsCase(name="start_null", bounds="start_range: {value: null}"),
    BoundsCase(name="end_null", bounds="end_range: {value: null}"),
]


RENAME_NUMBER_POOL = """
mutation RenameNumberPool($id: String!, $name: String!) {
  CoreNumberPoolUpdate(data: {id: $id, name: {value: $name}}) {
    ok
    object { name { value } }
  }
}
"""


UPDATE_NUMBER_POOL_BOUND = """
mutation UpdateNumberPool($id: String!) {
  CoreNumberPoolUpdate(data: {id: $id, %s}) {
    ok
  }
}
"""


class TestNumberPoolUpdate:
    """Bounds validation on pool update.

    The schema is loaded once for the class; every test creates pools under names of its own.
    """

    @pytest.fixture(scope="class")
    async def ticket_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> None:
        await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
        default_branch_scope_class.update_schema_hash()

    async def test_update_untouched_bounds_are_not_validated(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        """An update that leaves the bounds alone succeeds whatever the pool holds in them."""
        pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
        await pool.new(db=db, name="bound-less", node="TestingTicket", node_attribute="ticket_id")
        await pool.save(db=db)

        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=RENAME_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": pool.get_id(), "name": "bound-less-renamed"},
        )

        assert not result.errors
        assert result.data
        assert result.data["CoreNumberPoolUpdate"]["object"]["name"]["value"] == "bound-less-renamed"

        reloaded = await NodeManager.get_one(id=pool.get_id(), db=db, branch=default_branch_scope_class)
        assert reloaded is not None
        assert (reloaded.start_range.value, reloaded.end_range.value) == (None, None)

    @pytest.mark.parametrize("case", CLEARED_BOUND_CASES, ids=lambda case: case.name)
    async def test_update_rejects_clearing_a_bound(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None, case: BoundsCase
    ) -> None:
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        created = await graphql(
            schema=gql_params.schema,
            source=CREATE_NUMBER_POOL_WITH_BOUNDS % "start_range: {value: 10}, end_range: {value: 20}",
            context_value=gql_params.context,
            root_value=None,
            variable_values={"name": f"clearing-pool-{case.name}"},
        )
        assert not created.errors
        assert created.data
        pool_id = created.data["CoreNumberPoolCreate"]["object"]["id"]

        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_NUMBER_POOL_BOUND % case.bounds,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": pool_id},
        )

        assert [error.message for error in result.errors or []] == [BOUNDS_NOT_CLEARABLE]

        pool = await NodeManager.get_one(id=pool_id, db=db, branch=default_branch_scope_class)
        assert pool is not None
        assert (pool.start_range.value, pool.end_range.value) == (10, 20)
