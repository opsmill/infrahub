from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.schema.attribute_kind_update import (
    AttributeKindUpdateMigration,
    AttributeKindUpdateMigrationQuery,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.db_snapshot import DbSnapshotter
from tests.helpers.edge_timestamps import assert_edge_timestamps
from tests.helpers.schema import load_schema

CAR_SCHEMA_TEXT = {
    "version": "1.0",
    "nodes": [
        {
            "name": "Car",
            "namespace": "Test",
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "description", "kind": "Text"},  # Text is indexed
            ],
        }
    ],
}


async def check_attribute_value_vertices(db: InfrahubDatabase, value: str) -> tuple[int, int]:
    """Return number of indexed and non-indexed AttributeValue vertices for a given value."""
    query = "MATCH (av:AttributeValue) WHERE av.value = $value RETURN 'AttributeValueIndexed' IN labels(av) AS is_indexed, count(av) AS num_vertices"
    results = await db.execute_query(query=query, params={"value": value})
    num_indexed, num_non_indexed = 0, 0
    for result in results:
        if result["is_indexed"]:
            num_indexed = result["num_vertices"]
        else:
            num_non_indexed = result["num_vertices"]
    return num_indexed, num_non_indexed


async def test_query_indexed_to_not_indexed(db: InfrahubDatabase, default_branch: Branch) -> None:
    """Test changing attribute kind from indexed (Text) to not indexed (TextArea)."""
    await load_schema(db=db, schema=SchemaRoot(**CAR_SCHEMA_TEXT))
    description = "A nice car"

    car = await Node.init(db=db, schema="TestCar")
    await car.new(db=db, name="Accord", description=description)
    await car.save(db=db)

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    # Change description from Text (indexed) to TextArea (not indexed)
    new_attr = new_car_schema.get_attribute(name="description")
    new_attr.kind = "TextArea"

    # check that only 1 "A nice car" AttributeValue vertex exists
    num_indexed, num_non_indexed = await check_attribute_value_vertices(db=db, value=description)
    assert num_indexed == 1
    assert num_non_indexed == 0

    migration = AttributeKindUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="description"),
    )
    query = await AttributeKindUpdateMigrationQuery.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)

    # Re-execute the query once to ensure that it won't change anything
    query = await AttributeKindUpdateMigrationQuery.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)

    # check that a non-indexed "A nice car" AttributeValue vertex was created
    num_indexed, num_non_indexed = await check_attribute_value_vertices(db=db, value=description)
    assert num_indexed == 1
    assert num_non_indexed == 1


async def test_migration_no_change_when_same_index_status(db: InfrahubDatabase, default_branch: Branch) -> None:
    """Test that migration does nothing when attribute indexing status doesn't change."""
    await load_schema(db=db, schema=SchemaRoot(**CAR_SCHEMA_TEXT))

    car = await Node.init(db=db, schema="TestCar")
    await car.new(db=db, name="Accord", description="A nice car")
    await car.save(db=db)

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    # Change description from Text to another indexed type (e.g., Number)
    new_attr = new_car_schema.get_attribute(name="description")
    new_attr.kind = "Number"

    migration = AttributeKindUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="description"),
    )

    # Migration should return early without executing any queries
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 0


async def test_migration_edge_timestamps(db: InfrahubDatabase, default_branch: Branch) -> None:
    """Verify edges created/modified during AttributeKindUpdateMigration use the 'at' timestamp."""
    await load_schema(db=db, schema=SchemaRoot(**CAR_SCHEMA_TEXT))

    car = await Node.init(db=db, schema="TestCar")
    await car.new(db=db, name="Accord", description="A nice car")
    await car.save(db=db)

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    # Change description from Text (indexed) to TextArea (not indexed)
    new_attr = new_car_schema.get_attribute(name="description")
    new_attr.kind = "TextArea"

    # 1. Snapshot before migration
    snapshotter = DbSnapshotter(db)
    before_snapshot = await snapshotter.snapshot()

    # 2. Create explicit timestamp
    at = Timestamp()
    at_str = at.to_string()

    # 3. Execute migration
    migration = AttributeKindUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="description"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=default_branch)
    assert not execution_result.errors

    # 4. Validate edge timestamps
    after_snapshot = await snapshotter.snapshot()
    assert_edge_timestamps(before_snapshot, after_snapshot, at_str)
