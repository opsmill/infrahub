from typing import Any

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_remove import (
    NodeRemoveMigration,
    NodeRemoveMigrationQueryIn,
    NodeRemoveMigrationQueryOut,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase
from tests.component.core.migrations.schema.test_node_kind_update import validate_node_relationships
from tests.db_snapshot import DbSnapshotter
from tests.helpers.db_validation import verify_graph
from tests.helpers.edge_timestamps import assert_edge_timestamps
from tests.helpers.schema import load_schema


async def test_query_out_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    candidate_schema.delete(name="TestCar")

    assert await count_nodes(db=db, label="TestCar") == 2

    count_rels = await count_relationships(db=db)

    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )
    query = await NodeRemoveMigrationQueryOut.init(db=db, branch=default_branch, migration=migration)

    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 2

    # we expect 25 new relationships per TestCar, 50 TOTAL:
    # - 9 deleted parent edges (7 attributes, 1 outbound relationship, 1 IS_PART_OF)
    # - 16 deleted sub-edges (HAS_VALUE + IS_PROTECTED per attribute = 14, plus
    #   far-side IS_RELATED + IS_PROTECTED per outbound relationship = 2)
    assert await count_relationships(db=db) == count_rels + 50
    assert await count_nodes(db=db, label="TestCar") == 2

    # Re-execute the query once to ensure that it won't change anything
    query = await NodeRemoveMigrationQueryOut.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0
    assert await count_relationships(db=db) == count_rels + 50
    assert await count_nodes(db=db, label="TestCar") == 2


async def test_query_in_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    """This test is a bit silly for now because there is nothing to migrate but it least we validate that the generated query is valid"""

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    candidate_schema.delete(name="TestCar")

    assert await count_nodes(db=db, label="TestCar") == 2

    count_rels = await count_relationships(db=db)

    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )
    query = await NodeRemoveMigrationQueryIn.init(db=db, branch=default_branch, migration=migration)

    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0

    # we expect 0 new relationships because there is no inbound relationships defined currently
    assert await count_relationships(db=db) == count_rels + 0
    assert await count_nodes(db=db, label="TestCar") == 2

    # Re-execute the query once to ensure that it won't change anything
    query = await NodeRemoveMigrationQueryIn.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0
    assert await count_relationships(db=db) == count_rels + 0
    assert await count_nodes(db=db, label="TestCar") == 2


async def test_migration_aware(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    candidate_schema.delete(name="TestCar")

    # 1. Snapshot before migration
    snapshotter = DbSnapshotter(db)
    before_snapshot = await snapshotter.snapshot()

    # 2. Create explicit timestamp
    at = Timestamp()
    at_str = at.to_string()

    # 3. Count nodes and relationships before migration
    assert await count_nodes(db=db, label="TestCar") == 2
    count_rels = await count_relationships(db=db)

    # 4. Execute migration
    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2

    # 5. Validate nodes and relationships after migration
    assert await count_relationships(db=db) == count_rels + 50
    assert await count_nodes(db=db, label="TestCar") == 2

    # 6. Validate edge timestamps
    after_snapshot = await snapshotter.snapshot()
    assert_edge_timestamps(before_snapshot, after_snapshot, at_str)

    # 7. Validate node relationships
    await validate_node_relationships(node=car_accord_main, db=db, branch=default_branch)
    await validate_node_relationships(node=car_camry_main, db=db, branch=default_branch)

    # 8. Validate graph integrity
    await verify_graph(db=db)


async def test_migration_aware_inbound_relationship(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    """Remove TestPerson, exercising the IN query path for IS_RELATED.

    TestPerson.cars is defined with `direction: inbound`, so IS_RELATED edges from
    TestPerson's perspective are stored as `Relationship -> TestPerson`. Removing
    TestPerson must close the Relationship vertex's other sub-edges (IS_PROTECTED,
    far-side IS_RELATED to TestCar) — verify_graph would otherwise flag orphaned
    active sub-edges.
    """
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    candidate_schema.delete(name="TestPerson")

    # car_accord_main creates person_john_main, car_camry_main creates person_jane_main
    assert await count_nodes(db=db, label="TestPerson") == 2
    assert await count_nodes(db=db, label="TestCar") == 2

    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name="TestPerson"),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestPerson"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors

    # Cars themselves remain; only TestPerson nodes' edges are torn down.
    assert await NodeManager.count(db=db, schema="TestCar", branch=default_branch) == 2
    assert await NodeManager.count(db=db, schema="TestPerson", branch=default_branch) == 0

    await verify_graph(db=db)


async def test_migration_agnostic_relationship(
    db: InfrahubDatabase, default_branch: Branch, car_person_branch_agnostic_schema: dict[str, Any]
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
    candidate_schema.delete(name="TestCar")

    assert await count_nodes(db=db, label="TestCar") == 1

    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 1
    assert await count_nodes(db=db, label="TestCar") == 1

    await validate_node_relationships(node=person_john, db=db, branch=registry.get_global_branch())
    await validate_node_relationships(node=car, db=db, branch=registry.get_global_branch())

    await verify_graph(db=db)


async def test_migration_metadata(db: InfrahubDatabase, car_accord_main: Node, branch: Branch) -> None:
    """Test that metadata is set correctly when removing a node."""
    schema = registry.schema.get_schema_branch(name=branch.name)
    candidate_schema = schema.duplicate()
    candidate_schema.delete(name="TestCar")

    test_user_id = "test-metadata-user"
    migration_time = Timestamp()

    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )
    execution_result = await migration.execute(
        migration_input=MigrationInput(db=db, at=migration_time, user_id=test_user_id), branch=branch
    )
    assert not execution_result.errors

    await verify_graph(db=db)

    # Query for the deleted Node and its edge metadata
    query = """
    MATCH (n:TestCar {uuid: $node_uuid})-[r:IS_PART_OF {branch: $branch, status: "deleted"}]->(:Root)
    RETURN r.from_user_id as from_user_id, r.from as from_time, n.updated_at as updated_at, n.updated_by as updated_by
    """
    results = await db.execute_query(
        query=query,
        params={"node_uuid": car_accord_main.id, "branch": branch.name},
    )
    assert len(results) == 1, "Expected exactly one deleted IS_PART_OF edge"
    assert results[0]["from_user_id"] == test_user_id
    assert results[0]["from_time"] == migration_time.to_string()
    if branch.is_default:
        assert results[0]["updated_at"] == migration_time.to_string()
        assert results[0]["updated_by"] == test_user_id

    # Query for the deleted Attributes/Relationships
    query = """
    MATCH (n:TestCar {uuid: $node_uuid})
    MATCH (n)-[r:HAS_ATTRIBUTE|IS_RELATED {branch: $branch, status: "deleted"}]->(field)
    RETURN r.from_user_id as from_user_id, r.from as from_time,
        field.updated_at as updated_at, field.updated_by as updated_by,
        field.name AS name, field.uuid AS uuid
    """
    results = await db.execute_query(
        query=query,
        params={"node_uuid": car_accord_main.id, "branch": branch.name},
    )
    for result in results:
        name = result["name"]
        uuid = result["uuid"]
        assert result["from_user_id"] == test_user_id, f"Wrong from_user_id on edge to {name} ({uuid})"
        assert result["from_time"] == migration_time.to_string(), f"Wrong from_time on edge to {name} ({uuid})"
        if branch.is_default:
            assert result["updated_at"] == migration_time.to_string(), f"Wrong updated_at on {name} ({uuid})"
            assert result["updated_by"] == test_user_id, f"Wrong updated_by on {name} ({uuid})"
