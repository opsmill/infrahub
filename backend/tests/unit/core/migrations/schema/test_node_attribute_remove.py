from typing import Any

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SYSTEM_USER_ID, HashableModelState, MetadataOptions, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.migrations.schema.node_attribute_remove import (
    NodeAttributeRemoveMigration,
    NodeAttributeRemoveMigrationQuery01,
)
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase


async def test_query_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    attr = car_schema.get_attribute(name="color")
    attr.state = HashableModelState.ABSENT

    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    migration = NodeAttributeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    query = await NodeAttributeRemoveMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 2

    # We expect 6 more relationships because there are 2 attributes with 3 relationships each
    assert await count_relationships(db=db) == count_rels + 6
    assert await count_nodes(db=db, label="Attribute") == count_attr_node

    # Re-execute the query once to ensure that it won't change anything
    query = await NodeAttributeRemoveMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0
    assert await count_nodes(db=db, label="Attribute") == count_attr_node
    assert await count_relationships(db=db) == count_rels + 6


async def test_query_default_branch_generic_with_override(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics_unregistered: dict[str, Any]
) -> None:
    for node_schema_dict in car_person_schema_generics_unregistered["nodes"]:
        if node_schema_dict["name"] == "ElectricCar":
            node_schema_dict["attributes"].append(
                {"name": "color", "kind": "Text", "default_value": "#555555", "max_length": 8}
            )
    schema_root = SchemaRoot(**car_person_schema_generics_unregistered)
    schema = registry.schema.register_schema(schema=schema_root, branch=default_branch.name)

    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema="TestPerson")
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)
    e_car = await Node.init(db=db, schema="TestElectricCar")
    await e_car.new(db=db, name="volt", nbr_seats=3, nbr_engine=4, owner=p1, color="#aaabbbc")
    await e_car.save(db=db)
    g_car = await Node.init(db=db, schema="TestGazCar")
    await g_car.new(db=db, name="nolt", nbr_seats=4, mpg=25, owner=p2)
    await g_car.save(db=db)

    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    attr = car_schema.get_attribute(name="color")
    attr.state = HashableModelState.ABSENT

    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    migration = NodeAttributeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    query = await NodeAttributeRemoveMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 1

    # We expect 6 more relationships because there are 2 attributes with 3 relationships each
    assert await count_relationships(db=db) == count_rels + 3
    assert await count_nodes(db=db, label="Attribute") == count_attr_node

    # Re-execute the query once to ensure that it won't change anything
    query = await NodeAttributeRemoveMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0
    assert await count_nodes(db=db, label="Attribute") == count_attr_node
    assert await count_relationships(db=db) == count_rels + 3


async def test_migration(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    attr = car_schema.get_attribute(name="color")
    attr.state = HashableModelState.ABSENT

    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    migration = NodeAttributeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )

    execution_result = await migration.execute(db=db, branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2
    assert await count_nodes(db=db, label="Attribute") == count_attr_node
    assert await count_relationships(db=db) == count_rels + 6


async def test_migration_metadata(db: InfrahubDatabase, car_accord_main: Node, branch: Branch) -> None:
    """Test that metadata is set correctly when removing an attribute."""
    schema = registry.schema.get_schema_branch(name=branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    attr = car_schema.get_attribute(name="color")
    attr.state = HashableModelState.ABSENT

    test_user_id = "test-metadata-user"
    migration_time = Timestamp()

    migration = NodeAttributeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    execution_result = await migration.execute(db=db, branch=branch, at=migration_time, user_id=test_user_id)
    assert not execution_result.errors

    updated_car = await NodeManager.get_one(
        db=db,
        branch=branch,
        id=car_accord_main.id,
        include_metadata=MetadataQueryOptions(node_level=MetadataOptions.USER_TIMESTAMPS),
        fields={"color": True},
    )
    assert updated_car._get_created_at() < migration_time
    assert updated_car._get_created_by() == SYSTEM_USER_ID
    assert updated_car._get_updated_at() == migration_time
    assert updated_car._get_updated_by() == test_user_id

    # Query for the deleted attribute edges and verify metadata
    query = """
    MATCH (n:TestCar {uuid: $node_uuid})-[r:HAS_ATTRIBUTE {branch: $branch, status: "deleted"}]->(attr:Attribute {name: "color"})
    RETURN r.from_user_id as from_user_id, r.from as from_time, n.updated_at as updated_at, n.updated_by as updated_by
    """
    results = await db.execute_query(
        query=query,
        params={"node_uuid": car_accord_main.id, "branch": branch.name},
    )
    assert len(results) > 0, "Expected at least one deleted HAS_ATTRIBUTE edge"
    assert results[0]["from_user_id"] == test_user_id
    assert results[0]["from_time"] == migration_time.to_string()
    if branch.is_default:
        assert results[0]["updated_at"] == migration_time.to_string()
        assert results[0]["updated_by"] == test_user_id
