from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SYSTEM_USER_ID, MetadataOptions, RelationshipHierarchyDirection, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration, NodeKindUpdateMigrationQuery01
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.query.node import NodeGetHierarchyQuery
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase
from tests.constants import TestKind
from tests.db_snapshot import DbSnapshotter
from tests.helpers.db_validation import validate_node_relationships, verify_no_duplicate_paths
from tests.helpers.edge_timestamps import assert_edge_timestamps
from tests.helpers.schema import LOCATION_SCHEMA, load_schema


async def test_query_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    candidate_schema.delete(name="TestCar")
    car_schema.name = "NewCar"
    car_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewCar", schema=car_schema)
    assert car_schema.kind == "Test2NewCar"

    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 0

    count_rels = await count_relationships(db=db)

    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"),
    )
    query = await NodeKindUpdateMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 2

    # we expect 14 new relationships per TestCar, 36 TOTAL
    # 2 x 8 attributes = 16
    # 2 x 1 relationship = 2
    # 2 for the root node = 2
    assert await count_relationships(db=db) == count_rels + 36
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 2

    # Re-execute the query once to ensure that it won't change anything
    query = await NodeKindUpdateMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0
    assert await count_relationships(db=db) == count_rels + 36
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 2


async def test_migration_aware_relationship(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    candidate_schema.delete(name="TestCar")
    car_schema.name = "NewCar"
    car_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewCar", schema=car_schema)
    assert car_schema.kind == "Test2NewCar"

    # 1. Snapshot before migration
    snapshotter = DbSnapshotter(db)
    before_snapshot = await snapshotter.snapshot()

    # 2. Create explicit timestamp
    at = Timestamp()
    at_str = at.to_string()

    # 3. Count nodes and relationships before migration
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 0
    count_rels = await count_relationships(db=db)

    # 4. Execute migration
    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="namespace"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2

    # 5. Validate nodes and relationships after migration
    assert await count_relationships(db=db) == count_rels + 36
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 2

    # 6. Validate edge timestamps
    after_snapshot = await snapshotter.snapshot()
    assert_edge_timestamps(before_snapshot, after_snapshot, at_str)

    # 7. Validate node relationships
    await validate_node_relationships(node=car_accord_main, db=db, branch=default_branch)
    await validate_node_relationships(node=car_camry_main, db=db, branch=default_branch)


async def test_migration_agnostic_relationship(
    db: InfrahubDatabase, default_branch: Branch, car_person_branch_agnostic_schema
) -> None:
    await load_schema(db=db, schema=SchemaRoot(**car_person_branch_agnostic_schema))

    person_john = await Node.init(db=db, schema="TestPerson")
    await person_john.new(db=db, name={"value": "John"})
    await person_john.save(db=db)

    car = await Node.init(db=db, schema="TestCar")
    await car.new(db=db, name="yaris", agnostic_owner=person_john.id)
    await car.save(db=db)

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    candidate_schema.delete(name="TestCar")
    car_schema.name = "NewCar"
    car_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewCar", schema=car_schema)
    assert car_schema.kind == "Test2NewCar"

    assert await count_nodes(db=db, label="TestCar") == 1
    assert await count_nodes(db=db, label="Test2NewCar") == 0

    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="namespace"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 1
    assert await count_nodes(db=db, label="TestCar") == 1
    assert await count_nodes(db=db, label="Test2NewCar") == 1

    await validate_node_relationships(node=person_john, db=db, branch=registry.get_global_branch())
    await validate_node_relationships(node=car, db=db, branch=registry.get_global_branch())


async def test_migration_hierarchy(db: InfrahubDatabase, default_branch: Branch) -> None:
    await load_schema(db=db, schema=LOCATION_SCHEMA)

    continent_europe = await Node.init(db=db, schema=TestKind.CONTINENT)
    await continent_europe.new(db=db, name={"value": "Europe"}, shortname={"value": "EU"})
    await continent_europe.save(db=db)

    country_france = await Node.init(db=db, schema=TestKind.COUNTRY)
    await country_france.new(db=db, name="France", shortname={"value": "FR"}, parent=continent_europe.id)
    await country_france.save(db=db)

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    continent_schema = candidate_schema.get(name=TestKind.CONTINENT)
    candidate_schema.delete(name=TestKind.CONTINENT)
    continent_schema.name = "NewContinent"
    continent_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewContinent", schema=continent_schema)
    assert continent_schema.kind == "Test2NewContinent"
    candidate_schema.get(name=TestKind.COUNTRY, duplicate=False).parent = "Test2NewContinent"

    assert await count_nodes(db=db, label=TestKind.CONTINENT) == 1
    assert await count_nodes(db=db, label="Test2NewContinent") == 0

    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name=TestKind.CONTINENT),
        new_node_schema=continent_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind=TestKind.CONTINENT, field_name="namespace"
        ),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 1
    assert await count_nodes(db=db, label=TestKind.CONTINENT) == 1
    assert await count_nodes(db=db, label="Test2NewContinent") == 1

    country_schema = schema.get(name=TestKind.COUNTRY, duplicate=False)
    assert country_schema.parent == "Test2NewContinent"

    hierarchy_query = await NodeGetHierarchyQuery.init(
        db=db,
        direction=RelationshipHierarchyDirection.ANCESTORS,
        node_id=country_france.id,
        node_schema=country_schema,
        branch=default_branch,
    )
    await hierarchy_query.execute(db=db)
    assert list(hierarchy_query.get_peer_ids()) == [continent_europe.get_id()]


async def test_inheritance_migration_on_branch_and_main(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main, person_alfred_main: Node
) -> None:
    # 0. add a deleted relationship
    accord_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    await accord_main.owner.update(db=db, data=person_alfred_main.id)
    await accord_main.save(db=db)

    # 1. Create a new branch
    branch = await create_branch(db=db, branch_name="test-migration-branch")

    # 2. Run NodeKindUpdateMigration on the new branch
    schema = registry.schema.get_schema_branch(name=branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get_node(name="TestCar")
    candidate_schema.delete(name="TestCar")
    car_schema.inherit_from = ["GenericThing"]
    candidate_schema.set(name="TestCar", schema=car_schema)

    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="inherit_from"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2

    # 3. Run the same NodeKindUpdateMigration on the default_branch
    schema_default = registry.schema.get_schema_branch(name=default_branch.name)
    migration_default = NodeKindUpdateMigration(
        previous_node_schema=schema_default.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="inherit_from"),
    )

    execution_result_default = await migration_default.execute(
        migration_input=MigrationInput(db=db), branch=default_branch
    )
    assert not execution_result_default.errors

    await verify_no_duplicate_paths(db=db)


async def test_migration_metadata(db: InfrahubDatabase, car_accord_main: Node, branch: Branch) -> None:
    """Test that metadata is set correctly when updating node kind."""
    car_created_at = car_accord_main._get_created_at()
    schema = registry.schema.get_schema_branch(name=branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    candidate_schema.delete(name="TestCar")
    car_schema.name = "NewCar"
    car_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewCar", schema=car_schema)

    test_user_id = "test-metadata-user"
    migration_time = Timestamp()

    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"),
    )
    execution_result = await migration.execute(db=db, branch=branch, at=migration_time, user_id=test_user_id)
    assert not execution_result.errors

    registry.schema.set_schema_branch(name=branch.name, schema=candidate_schema)

    updated_car = await NodeManager.get_one(
        db=db,
        branch=branch,
        id=car_accord_main.id,
        include_metadata=MetadataQueryOptions(
            node_level=MetadataOptions.USER_TIMESTAMPS,
            attribute_level=MetadataOptions.USER_TIMESTAMPS,
            relationship_level=MetadataOptions.USER_TIMESTAMPS,
        ),
        prefetch_relationships=True,
    )
    assert updated_car._get_created_at() == car_created_at
    assert updated_car._get_created_by() == SYSTEM_USER_ID
    assert updated_car._get_updated_at() == migration_time
    assert updated_car._get_updated_by() == test_user_id
    for attr_name in car_schema.attribute_names:
        attr = updated_car.get_attribute(name=attr_name)
        assert attr._get_created_at() == car_created_at
        assert attr._get_created_by() == SYSTEM_USER_ID
        assert attr._get_updated_at() == attr._get_created_at()
        assert attr._get_updated_by() == SYSTEM_USER_ID
    rel_manager = updated_car.get_relationship(name="owner")
    rel = await rel_manager.get(db=db)
    assert rel._get_created_at() == car_created_at
    assert rel._get_created_by() == SYSTEM_USER_ID
    assert rel._get_updated_at() == rel._get_created_at()
    assert rel._get_updated_by() == SYSTEM_USER_ID

    # Query for the NEW active node edges and verify metadata
    query = """
    MATCH (n:Test2NewCar {uuid: $node_uuid})-[r {branch: $branch, status: "active", from: $migration_time}]-()
    RETURN DISTINCT r.from_user_id as from_user_id
    """
    results = await db.execute_query(
        query=query,
        params={"node_uuid": car_accord_main.id, "branch": branch.name, "migration_time": migration_time.to_string()},
    )
    assert len(results) == 1, "Expected exactly one active edge on migrated node"
    assert results[0]["from_user_id"] == test_user_id

    # Query for the OLD deleted node edges and verify metadata
    query = """
    MATCH (n:TestCar {uuid: $node_uuid})-[r {branch: $branch, status: "deleted", from: $migration_time}]-()
    RETURN DISTINCT r.from_user_id as from_user_id
    """
    results = await db.execute_query(
        query=query,
        params={"node_uuid": car_accord_main.id, "branch": branch.name, "migration_time": migration_time.to_string()},
    )
    assert len(results) == 1, "Expected exactly one deleted edge on old node"
    assert results[0]["from_user_id"] == test_user_id
