import uuid

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.initialization import (
    create_branch,
)
from infrahub.core.migrations.schema.attribute_name_update import (
    AttributeNameUpdateMigration,
    AttributeNameUpdateMigrationQuery01,
)
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase


async def test_query_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main, car_profile1_main
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="color")
    prev_attr.id = str(uuid.uuid4())
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="color")
    new_attr.name = "new-color"
    new_attr.id = prev_attr.id

    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    migration = AttributeNameUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="new-color"),
    )
    query = await AttributeNameUpdateMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)

    assert query.get_nbr_migrations_executed() == 3

    # We expect 9 more relationships because there are 3 attributes with 3 relationships each
    assert await count_relationships(db=db) == count_rels + 9
    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 3

    # Re-execute the query once to ensure that it won't change anything
    query = await AttributeNameUpdateMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0

    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 3
    assert await count_relationships(db=db) == count_rels + 9


async def test_query_branch1(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main, car_profile1_main
) -> None:
    branch1 = await create_branch(db=db, branch_name="branch1", isolated=True)

    schema = registry.schema.get_schema_branch(name=branch1.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="color")
    prev_attr.id = str(uuid.uuid4())
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="color")
    new_attr.name = "new-color"
    new_attr.id = prev_attr.id

    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    migration = AttributeNameUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="new-color"),
    )
    query = await AttributeNameUpdateMigrationQuery01.init(db=db, branch=branch1, migration=migration)

    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 3

    # We expect 18 more relationships because there are 3 attributes with 6 relationships each
    assert await count_relationships(db=db) == count_rels + 18
    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 3

    # Re-execute the query once to ensure that it won't change anything
    query = await AttributeNameUpdateMigrationQuery01.init(db=db, branch=branch1, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0

    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 3
    assert await count_relationships(db=db) == count_rels + 18


async def test_migration(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main, car_profile1_main
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="color")
    prev_attr.id = str(uuid.uuid4())
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="color")
    new_attr.name = "new-color"
    new_attr.id = prev_attr.id

    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    migration = AttributeNameUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="new-color"),
    )

    execution_result = await migration.execute(db=db, branch=default_branch)
    assert not execution_result.errors

    assert execution_result.nbr_migrations_executed == 3

    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 3
    assert await count_relationships(db=db) == count_rels + 9


async def test_migration_with_user_id(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_profile1_main: Node
) -> None:
    """Test that the user_id passed to migration.execute() is correctly set on the renamed attribute's metadata."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="color")
    prev_attr.id = str(uuid.uuid4())
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="color")
    new_attr.name = "new-color"
    new_attr.id = prev_attr.id

    migration = AttributeNameUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="new-color"),
    )

    test_user_id = "test-rename-migration-user"
    migration_time = Timestamp()
    execution_result = await migration.execute(db=db, branch=default_branch, at=migration_time, user_id=test_user_id)

    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2

    # Query for the new attribute edges created by the migration and verify user_id metadata
    query = """
    MATCH (n:TestCar {uuid: $car_uuid})-[:HAS_ATTRIBUTE]->(attr:Attribute {name: "new-color"})
    MATCH (attr)-[r {status: "active"}]-()
    RETURN r.from_user_id as from_user_id, r.from as from_time
    """
    results = await db.execute_query(query=query, params={"car_uuid": car_accord_main.id})

    # All active edges on the renamed attribute should have the test user_id
    assert len(results) > 0, "Expected at least one active edge on renamed attribute"
    for record in results:
        assert record["from_user_id"] == test_user_id
        assert record["from_time"] == migration_time.to_string()
