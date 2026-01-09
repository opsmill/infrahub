import uuid

from infrahub_sdk.schema.main import RelationshipDirection

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m023_deduplicate_cardinality_one_relationships import Migration023
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase

# redis is required as we will call `initialization` later


async def test_migration_023(db: InfrahubDatabase, branch, car_person_schema, redis) -> None:
    """
    Reproduce corrupted state where two nodes would be connected by multiple relationships while relationship
    cardinality is one.
    """

    person_john = await Node.init(schema="TestPerson", db=db, branch=branch)
    await person_john.new(db=db, name="John")
    await person_john.save(db=db)

    person_maria = await Node.init(schema="TestPerson", db=db, branch=branch)
    await person_maria.new(db=db, name="Maria")
    await person_maria.save(db=db)

    car_honda = await Node.init(schema="TestCar", db=db, branch=branch)
    await car_honda.new(db=db, name="honda", owner=person_john, driver=person_john)
    await car_honda.save(db=db)

    car_suzuki = await Node.init(schema="TestCar", db=db, branch=branch)
    await car_suzuki.new(db=db, name="suzuki", owner=person_john, driver=person_john)
    await car_suzuki.save(db=db)

    # Make sure to also test bidirectional relationships.
    driver_rel = [
        rel for rel in car_person_schema.get("TestPerson").relationships if rel.identifier == "cars_driven__driver"
    ]
    assert len(driver_rel) == 1
    assert driver_rel[0].direction == RelationshipDirection.BIDIR

    before_time = "2000-03-04T15:03:59.595725Z"

    await add_extra_relationship(
        db=db,
        before_time=before_time,
        branch=branch,
        node_1_id=car_honda.id,
        node_2_id=person_maria.id,
        rel_name="testcar__testperson",
    )
    await add_extra_relationship(
        db=db,
        before_time=before_time,
        branch=branch,
        node_1_id=car_honda.id,
        node_2_id=person_maria.id,
        rel_name="cars_driven__driver",
    )
    await add_extra_relationship(
        db=db,
        before_time=before_time,
        branch=branch,
        node_1_id=car_suzuki.id,
        node_2_id=person_maria.id,
        rel_name="testcar__testperson",
    )
    await add_extra_relationship(
        db=db,
        before_time=before_time,
        branch=branch,
        node_1_id=car_suzuki.id,
        node_2_id=person_maria.id,
        rel_name="cars_driven__driver",
    )

    migration = Migration023()
    await migration.execute(migration_input=MigrationInput(db=db))
    await migration.validate_migration(db=db)

    await check_number_path_between_nodes(
        db=db, node_id_1=car_honda.id, node_id_2=person_maria.id, expected_path_number=0
    )
    await check_number_path_between_nodes(
        db=db, node_id_1=car_suzuki.id, node_id_2=person_maria.id, expected_path_number=0
    )

    # 2 paths: owner and driver relationships
    await check_number_path_between_nodes(
        db=db, node_id_1=car_honda.id, node_id_2=person_john.id, expected_path_number=2
    )
    await check_number_path_between_nodes(
        db=db, node_id_1=car_suzuki.id, node_id_2=person_john.id, expected_path_number=2
    )

    car_honda = await NodeManager.get_one(
        id=car_honda.id, kind="TestCar", db=db, prefetch_relationships=True, branch=branch
    )
    assert car_honda.driver.get_one().peer_id == person_john.id
    assert car_honda.owner.get_one().peer_id == person_john.id

    car_suzuki = await NodeManager.get_one(
        id=car_suzuki.id, kind="TestCar", db=db, prefetch_relationships=True, branch=branch
    )
    assert car_suzuki.driver.get_one().peer_id == person_john.id
    assert car_suzuki.owner.get_one().peer_id == person_john.id

    person_john = await NodeManager.get_one(
        id=person_john.id, kind="TestPerson", db=db, prefetch_relationships=True, branch=branch
    )
    assert {rel.peer_id for rel in person_john.cars} == {car_honda.id, car_suzuki.id}

    person_maria = await NodeManager.get_one(
        id=person_maria.id, kind="TestPerson", db=db, prefetch_relationships=True, branch=branch
    )
    rels = await person_maria.cars.get_relationships(db=db)
    assert len(rels) == 0


async def add_extra_relationship(db, node_1_id, node_2_id, before_time, branch, rel_name) -> None:
    add_extra_relationship_query = """
    MATCH (node_1: Node {uuid: $node_1_id})
    MATCH (node_2: Node {uuid: $node_2_id})
    CREATE (node_1)-[:IS_RELATED {status: "active", from: $from, branch: $branch, branch_level: $branch_level}] \
    ->(rel: Relationship {name: $rel_name, branch_support: "aware", uuid: $new_rel_uuid}) \
    -[:IS_RELATED {status: "active", from: $from, branch: $branch, branch_level: $branch_level}] \
    ->(node_2)
    RETURN node_1, rel, node_2
    """
    await db.execute_query(
        query=add_extra_relationship_query,
        name="add_extra_relationship_query",
        params={
            "node_1_id": node_1_id,
            "node_2_id": node_2_id,
            "from": before_time,
            "branch": branch.name,
            "new_rel_uuid": str(uuid.uuid4()),
            "rel_name": rel_name,
            "branch_level": 1 if branch.name in [registry.default_branch, GLOBAL_BRANCH_NAME] else 2,
        },
    )


async def check_number_path_between_nodes(db, node_id_1, node_id_2, expected_path_number) -> None:
    check_single_relationship_query = """
        MATCH path = (car:Node {uuid: $node_id_1})-[:IS_RELATED]-(rel: Relationship)-[:IS_RELATED]-(maria:Node {uuid: $node_id_2})
        RETURN COUNT(path) AS pathCount
    """
    results = await db.execute_query(
        query=check_single_relationship_query,
        name="check_single_relationship_query",
        params={"node_id_1": node_id_1, "node_id_2": node_id_2},
    )
    assert len(results) == 1
    assert results[0].get("pathCount") == expected_path_number
