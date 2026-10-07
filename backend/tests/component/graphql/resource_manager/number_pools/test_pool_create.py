import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.mutations.resource_manager.number_pools.pool import BOUNDS_REQUIRED, SHORTHAND_WITH_RANGES
from tests.helpers.graphql import graphql
from tests.helpers.schema import TICKET, load_schema

from .helpers import (
    CREATE_NUMBER_POOL,
    CREATE_NUMBER_POOL_WITH_BOUNDS,
    BoundsCase,
    bounds_input,
    create_pool,
    execute,
    range_bounds,
    ticket_pool_input,
)

UNKNOWN_RANGE_ID = "ffffffff-ffff-ffff-ffff-ffffffffffff"


MISSING_BOUND_CASES = [
    BoundsCase(name="start_only", bounds={"start_range": {"value": 1}}),
    BoundsCase(name="end_only", bounds={"end_range": {"value": 9}}),
    BoundsCase(name="start_null", bounds={"start_range": {"value": None}, "end_range": {"value": 9}}),
    BoundsCase(name="end_null", bounds={"start_range": {"value": 1}, "end_range": {"value": None}}),
]


NO_BOUNDS_CASES = [
    BoundsCase(name="neither_spelling", bounds={}),
    BoundsCase(name="both_null", bounds={"start_range": {"value": None}, "end_range": {"value": None}}),
    BoundsCase(name="empty_inputs", bounds={"start_range": {}, "end_range": {}}),
    BoundsCase(name="empty_ranges", bounds={"ranges": []}),
]


QUERY_POOL_WITH_RANGES = """
query PoolWithRanges($id: ID!) {
  CoreNumberPool(ids: [$id]) {
    edges {
      node {
        start_range { value }
        end_range { value }
        ranges { edges { node { start { value } end { value } allocation_weight { value } } } }
      }
    }
  }
}
"""


UNKNOWN_RANGE_MESSAGE = f"Unable to find the node {UNKNOWN_RANGE_ID} / CoreNumberPoolRange in the database."


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

    @pytest.mark.parametrize("case", MISSING_BOUND_CASES, ids=lambda case: case.name)
    async def test_create_requires_both_bounds(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None, case: BoundsCase
    ) -> None:
        pools_before = await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch_scope_class)
        ranges_before = await NodeManager.count(
            db=db, schema=InfrahubKind.NUMBERPOOLRANGE, branch=default_branch_scope_class
        )

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_NUMBER_POOL_WITH_BOUNDS,
            variables={"data": ticket_pool_input(name=f"bounds-pool-{case.name}", bounds=case.bounds)},
        )

        assert [error.message for error in result.errors or []] == [BOUNDS_REQUIRED]
        assert (
            await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch_scope_class)
            == pools_before
        )
        assert (
            await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOLRANGE, branch=default_branch_scope_class)
            == ranges_before
        )

    @pytest.mark.parametrize("case", NO_BOUNDS_CASES, ids=lambda case: case.name)
    async def test_create_without_bounds_yields_a_pool_without_range(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None, case: BoundsCase
    ) -> None:
        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_NUMBER_POOL_WITH_BOUNDS,
            variables={"data": ticket_pool_input(name=f"empty-pool-{case.name}", bounds=case.bounds)},
        )

        assert not result.errors
        assert result.data
        created = result.data["CoreNumberPoolCreate"]["object"]
        assert (created["start_range"]["value"], created["end_range"]["value"]) == (None, None)
        assert created["ranges"]["count"] == 0
        assert await range_bounds(db=db, pool_id=created["id"]) == []

    async def test_create_with_an_unknown_range_is_refused(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pools_before = await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch_scope_class)

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_NUMBER_POOL_WITH_BOUNDS,
            variables={
                "data": ticket_pool_input(name="unknown-range-pool", bounds={"ranges": [{"id": UNKNOWN_RANGE_ID}]})
            },
        )

        assert [error.message for error in result.errors or []] == [UNKNOWN_RANGE_MESSAGE]
        assert (
            await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch_scope_class)
            == pools_before
        )

    async def test_create_with_bounds_creates_the_single_range(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pool_id = await create_pool(
            db=db,
            branch=default_branch_scope_class,
            name="one-range-pool",
            bounds=bounds_input(start=10, end=20),
        )

        read = await execute(
            db=db, branch=default_branch_scope_class, source=QUERY_POOL_WITH_RANGES, variables={"id": pool_id}
        )

        assert not read.errors
        assert read.data
        node = read.data["CoreNumberPool"]["edges"][0]["node"]
        assert (node["start_range"]["value"], node["end_range"]["value"]) == (10, 20)
        assert [
            (edge["node"]["start"]["value"], edge["node"]["end"]["value"], edge["node"]["allocation_weight"]["value"])
            for edge in node["ranges"]["edges"]
        ] == [(10, 20, None)]

    async def test_create_accepts_equal_bounds(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_NUMBER_POOL_WITH_BOUNDS,
            variables={"data": ticket_pool_input(name="equal-bounds-pool", bounds=bounds_input(start=5, end=5))},
        )

        assert not result.errors
        assert result.data
        created = result.data["CoreNumberPoolCreate"]["object"]
        assert (created["start_range"]["value"], created["end_range"]["value"]) == (5, 5)
        assert created["ranges"]["count"] == 1
        assert await range_bounds(db=db, pool_id=created["id"]) == [(5, 5)]

    async def test_create_refuses_bounds_combined_with_ranges(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pools_before = await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch_scope_class)

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_NUMBER_POOL_WITH_BOUNDS,
            variables={
                "data": ticket_pool_input(
                    name="both-spellings-pool", bounds=bounds_input(start=1, end=9) | {"ranges": []}
                )
            },
        )

        assert [error.message for error in result.errors or []] == [SHORTHAND_WITH_RANGES]
        assert (
            await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch_scope_class)
            == pools_before
        )

    async def test_number_pool_creation_errors(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        pools_before = await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch_scope_class)
        ranges_before = await NodeManager.count(
            db=db, schema=InfrahubKind.NUMBERPOOLRANGE, branch=default_branch_scope_class
        )
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

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

        missing_end = await graphql(
            schema=gql_params.schema,
            source=CREATE_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"name": "pool1", "node": "TestingTicket", "node_attribute": "ticket_id", "start_range": 1},
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
        assert [error.message for error in missing_end.errors or []] == [BOUNDS_REQUIRED]
        assert (
            await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch_scope_class)
            == pools_before
        )
        assert (
            await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOLRANGE, branch=default_branch_scope_class)
            == ranges_before
        )

    async def test_pool_created_with_bounds_hands_out_numbers_from_its_range(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ticket_schema: None
    ) -> None:
        await initialize_registry(db=db)
        pool_id = await create_pool(
            db=db,
            branch=default_branch_scope_class,
            name="allocating-pool",
            bounds=bounds_input(start=100, end=101),
        )

        allocated = []
        for title in ("first", "second"):
            ticket = await Node.init(db=db, schema=TICKET.kind)
            await ticket.new(db=db, title=title, ticket_id={"from_pool": {"id": pool_id}})
            await ticket.save(db=db)
            allocated.append(ticket.get_attribute("ticket_id").value)

        assert allocated == [100, 101]
        exhausted = await Node.init(db=db, schema=TICKET.kind)
        with pytest.raises(ValidationError) as exc_info:
            await exhausted.new(db=db, title="third", ticket_id={"from_pool": {"id": pool_id}})

        assert exc_info.value.message == (
            f"Pool allocating-pool ({pool_id}) has no free number left in its ranges. at ticket_id.from_pool"
        )
