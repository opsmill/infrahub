import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.manager import registry as graphql_registry
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.helpers.graphql import graphql
from tests.helpers.schema import SNOW_TICKET_SCHEMA, TICKET, load_schema

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
      end_range { value }
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
