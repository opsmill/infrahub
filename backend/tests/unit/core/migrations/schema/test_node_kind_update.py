from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipHierarchyDirection, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration, NodeKindUpdateMigrationQuery01
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.query.node import NodeGetHierarchyQuery
from infrahub.core.schema import SchemaRoot
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase
from tests.constants import TestKind
from tests.helpers.db_validation import validate_node_relationships, verify_no_duplicate_paths
from tests.helpers.schema import LOCATION_SCHEMA, load_schema


async def test_query_default_branch(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
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
):
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
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="namespace"),
    )

    execution_result = await migration.execute(db=db, branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2
    assert await count_relationships(db=db) == count_rels + 36
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 2

    await validate_node_relationships(node=car_accord_main, db=db, branch=default_branch)
    await validate_node_relationships(node=car_camry_main, db=db, branch=default_branch)


async def test_migration_agnostic_relationship(
    db: InfrahubDatabase, default_branch: Branch, car_person_branch_agnostic_schema
):
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

    execution_result = await migration.execute(db=db, branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 1
    assert await count_nodes(db=db, label="TestCar") == 1
    assert await count_nodes(db=db, label="Test2NewCar") == 1

    await validate_node_relationships(node=person_john, db=db, branch=registry.get_global_branch())
    await validate_node_relationships(node=car, db=db, branch=registry.get_global_branch())


async def test_migration_hierarchy(db: InfrahubDatabase, default_branch: Branch):
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

    execution_result = await migration.execute(db=db, branch=default_branch)
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
):
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

    execution_result = await migration.execute(db=db, branch=branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2

    # 3. Run the same NodeKindUpdateMigration on the default_branch
    schema_default = registry.schema.get_schema_branch(name=default_branch.name)
    migration_default = NodeKindUpdateMigration(
        previous_node_schema=schema_default.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="inherit_from"),
    )

    execution_result_default = await migration_default.execute(db=db, branch=default_branch)
    assert not execution_result_default.errors

    await verify_no_duplicate_paths(db=db)
