import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.mutations.resource_manager.number_pools.pool import BOUNDS_REQUIRED
from tests.helpers.graphql import graphql
from tests.helpers.schema import TICKET, load_schema

from .helpers import CREATE_NUMBER_POOL, CREATE_NUMBER_POOL_WITH_BOUNDS, UNKNOWN_RANGE_ID, BoundsCase

MISSING_BOUNDS_CASES = [
    BoundsCase(name="neither_bound", bounds=""),
    BoundsCase(name="start_only", bounds="start_range: {value: 1}"),
    BoundsCase(name="end_only", bounds="end_range: {value: 9}"),
    BoundsCase(name="start_null", bounds="start_range: {value: null}, end_range: {value: 9}"),
    BoundsCase(name="end_null", bounds="start_range: {value: 1}, end_range: {value: null}"),
    BoundsCase(name="both_null", bounds="start_range: {value: null}, end_range: {value: null}"),
    BoundsCase(name="empty_inputs", bounds="start_range: {}, end_range: {}"),
    BoundsCase(name="ranges_without_bounds", bounds='ranges: [{id: "%s"}]' % UNKNOWN_RANGE_ID),
]


async def test_number_pool_creation_errors(
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


class TestNumberPoolCreate:
    """Bounds validation on pool creation.

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

    @pytest.mark.parametrize("case", MISSING_BOUNDS_CASES, ids=lambda case: case.name)
    async def test_create_requires_both_bounds(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None, case: BoundsCase
    ) -> None:
        pools_before = await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch_scope_class)
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_NUMBER_POOL_WITH_BOUNDS % case.bounds,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"name": f"bounds-pool-{case.name}"},
        )

        assert [error.message for error in result.errors or []] == [BOUNDS_REQUIRED]
        assert (
            await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch_scope_class)
            == pools_before
        )

    async def test_create_accepts_equal_bounds(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_NUMBER_POOL_WITH_BOUNDS % "start_range: {value: 5}, end_range: {value: 5}",
            context_value=gql_params.context,
            root_value=None,
            variable_values={"name": "equal-bounds-pool"},
        )

        assert not result.errors
        assert result.data
        created = result.data["CoreNumberPoolCreate"]["object"]
        assert (created["start_range"]["value"], created["end_range"]["value"]) == (5, 5)
