import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.pools.number_pool_repository import NumberPoolRepository
from tests.helpers.graphql import graphql
from tests.helpers.number_pool import add_pool_range
from tests.helpers.schema import TICKET, load_schema

from .helpers import (
    CREATE_NUMBER_POOL,
    DELETE_NUMBER_POOL,
    QUERY_NUMBER_POOL,
    UPDATE_NUMBER_POOL,
    execute,
    range_bounds,
    range_details,
    shorthand,
)

UPSERT_NUMBER_POOL = """
mutation UpsertNumberPool(
    $name: String!,
    $node: String!,
    $node_attribute: String!,
    $start_range: BigInt!,
    $end_range: BigInt!
  ) {
  CoreNumberPoolUpsert(
    data: {
      name: {value: $name},
      node: {value: $node},
      node_attribute: {value: $node_attribute},
      start_range: {value: $start_range},
      end_range: {value: $end_range}
    }
  ) {
    object {
      display_label
      id
      end_range { value }
    }
  }
}
"""


async def test_number_pool_update(
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
    assert await shorthand(db=db, pool_id=pool_id) == (10, 20)
    assert await range_bounds(db=db, pool_id=pool_id) == [(10, 20)]

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


class TestNumberPoolUpsertImmutableFields:
    """Tests for the immutable-field guard across CoreNumberPool update and upsert mutations.

    Schema is loaded once for the class. Each test creates its own pool (unique name) so
    there is no cross-test state dependency.
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

    async def test_upsert_identical_fields(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        ticket_schema: None,
    ) -> None:
        """Upsert with all identical values (including node/node_attribute) succeeds."""
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        create_ok = await graphql(
            schema=gql_params.schema,
            source=CREATE_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "name": "pool-upsert-1",
                "node": "TestingTicket",
                "node_attribute": "ticket_id",
                "start_range": 10,
                "end_range": 20,
            },
        )
        assert not create_ok.errors
        pool_id = create_ok.data["CoreNumberPoolCreate"]["object"]["id"]

        upsert_same = await graphql(
            schema=gql_params.schema,
            source=UPSERT_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "name": "pool-upsert-1",
                "node": "TestingTicket",
                "node_attribute": "ticket_id",
                "start_range": 10,
                "end_range": 20,
            },
        )
        assert not upsert_same.errors
        assert upsert_same.data
        assert upsert_same.data["CoreNumberPoolUpsert"]["object"]["id"] == pool_id
        assert await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch_scope_class) == 1
        assert await range_bounds(db=db, pool_id=pool_id) == [(10, 20)]

    async def test_upsert_mutable_fields(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        ticket_schema: None,
    ) -> None:
        """Upsert with unchanged node/node_attribute but updated range succeeds and persists the new range."""
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        create_ok = await graphql(
            schema=gql_params.schema,
            source=CREATE_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "name": "pool-upsert-2",
                "node": "TestingTicket",
                "node_attribute": "ticket_id",
                "start_range": 10,
                "end_range": 20,
            },
        )
        assert not create_ok.errors
        pool_id = create_ok.data["CoreNumberPoolCreate"]["object"]["id"]
        (pool_range,) = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)

        upsert_mutable = await graphql(
            schema=gql_params.schema,
            source=UPSERT_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "name": "pool-upsert-2",
                "node": "TestingTicket",
                "node_attribute": "ticket_id",
                "start_range": 10,
                "end_range": 30,
            },
        )
        assert not upsert_mutable.errors
        assert upsert_mutable.data
        assert upsert_mutable.data["CoreNumberPoolUpsert"]["object"]["id"] == pool_id
        assert upsert_mutable.data["CoreNumberPoolUpsert"]["object"]["end_range"]["value"] == 30

        pool = await NodeManager.get_one(id=pool_id, db=db, branch=default_branch_scope_class)
        assert pool is not None
        assert pool.get_attribute("end_range").value == 30
        assert await range_details(db=db, pool_id=pool_id) == [(pool_range.get_id(), 10, 30, None)]

    async def test_upsert_creating_a_pool_with_bounds_creates_its_range(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        ticket_schema: None,
    ) -> None:
        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPSERT_NUMBER_POOL,
            variables={
                "name": "pool-upsert-new",
                "node": "TestingTicket",
                "node_attribute": "ticket_id",
                "start_range": 40,
                "end_range": 60,
            },
        )

        assert not result.errors
        assert result.data
        pool_id = result.data["CoreNumberPoolUpsert"]["object"]["id"]
        assert await shorthand(db=db, pool_id=pool_id) == (40, 60)
        assert await range_bounds(db=db, pool_id=pool_id) == [(40, 60)]

    async def test_upsert_refuses_bounds_on_a_pool_with_several_ranges(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        ticket_schema: None,
    ) -> None:
        pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
        await pool.new(db=db, name="pool-upsert-multi", node="TestingTicket", node_attribute="ticket_id")
        await pool.save(db=db)
        low = await add_pool_range(db=db, pool=pool, start=1, end=5)
        high = await add_pool_range(db=db, pool=pool, start=10, end=15)

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPSERT_NUMBER_POOL,
            variables={
                "name": "pool-upsert-multi",
                "node": "TestingTicket",
                "node_attribute": "ticket_id",
                "start_range": 1,
                "end_range": 15,
            },
        )

        assert [error.message for error in result.errors or []] == [
            "start_range/end_range apply to a pool holding at most one range; this pool holds: "
            f"1-5 ({low.get_id()}), 10-15 ({high.get_id()}). Edit the ranges instead."
        ]
        assert await shorthand(db=db, pool_id=pool.get_id()) == (None, None)
        assert await range_bounds(db=db, pool_id=pool.get_id()) == [(1, 5), (10, 15)]

    async def test_update_with_unchanged_node_fields(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        ticket_schema: None,
    ) -> None:
        """CoreNumberPoolUpdate succeeds when node/node_attribute are present but unchanged.

        This exercises the Update mutation path (mutate_update guard) specifically —
        distinct from the upsert tests above which route through mutate_update_object.
        """
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        create_ok = await graphql(
            schema=gql_params.schema,
            source=CREATE_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "name": "pool-update-same",
                "node": "TestingTicket",
                "node_attribute": "ticket_id",
                "start_range": 10,
                "end_range": 20,
            },
        )
        assert not create_ok.errors
        pool_id = create_ok.data["CoreNumberPoolCreate"]["object"]["id"]

        update_same_values = await graphql(
            schema=gql_params.schema,
            source=UPDATE_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "id": pool_id,
                "node": "TestingTicket",
                "node_attribute": "ticket_id",
                "start_range": 10,
                "end_range": 25,
            },
        )
        assert not update_same_values.errors
        assert update_same_values.data["CoreNumberPoolUpdate"]["object"]["end_range"]["value"] == 25

        pool = await NodeManager.get_one(id=pool_id, db=db, branch=default_branch_scope_class)
        assert pool is not None
        assert pool.get_attribute("end_range").value == 25

    async def test_update_rejects_node_attribute_change(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        ticket_schema: None,
    ) -> None:
        """CoreNumberPoolUpdate rejects a payload that changes node_attribute."""
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        create_ok = await graphql(
            schema=gql_params.schema,
            source=CREATE_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "name": "pool-update-rej",
                "node": "TestingTicket",
                "node_attribute": "ticket_id",
                "start_range": 10,
                "end_range": 20,
            },
        )
        assert not create_ok.errors
        pool_id = create_ok.data["CoreNumberPoolCreate"]["object"]["id"]

        update_changed_attr = await graphql(
            schema=gql_params.schema,
            source=UPDATE_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "id": pool_id,
                "node": "TestingTicket",
                "node_attribute": "ticket_name",
            },
        )
        assert update_changed_attr.errors
        assert str(update_changed_attr.errors[0].message) == "The fields 'node' or 'node_attribute' can't be changed."

    async def test_update_rejects_node_change(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        ticket_schema: None,
    ) -> None:
        """CoreNumberPoolUpdate rejects a payload that changes node."""
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)

        create_ok = await graphql(
            schema=gql_params.schema,
            source=CREATE_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "name": "pool-update-node-rej",
                "node": "TestingTicket",
                "node_attribute": "ticket_id",
                "start_range": 10,
                "end_range": 20,
            },
        )
        assert not create_ok.errors
        pool_id = create_ok.data["CoreNumberPoolCreate"]["object"]["id"]

        update_changed_node = await graphql(
            schema=gql_params.schema,
            source=UPDATE_NUMBER_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={
                "id": pool_id,
                "node": "SomeDifferentModel",
                "node_attribute": "ticket_id",
            },
        )
        assert update_changed_node.errors
        assert str(update_changed_node.errors[0].message) == "The fields 'node' or 'node_attribute' can't be changed."
