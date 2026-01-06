from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.migrations.graph import Migration019
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot, core_models
from infrahub.core.timestamp import Timestamp, current_timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.db_validation import validate_node_relationships


async def test_migration_019(
    db: InfrahubDatabase,
    default_branch,
) -> None:
    """
    Reproduce corrupted state introduced by migration 12, and apply the migration fixing it.
    """

    schema = SchemaRoot(**core_models)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)

    test_group = await Node.init(db=db, schema="CoreStandardGroup")
    await test_group.new(db=db, name="test_group")
    await test_group.save(db=db)

    core_acc = await Node.init(db=db, schema="CoreAccount")
    await core_acc.new(db=db, name="core_acc", account_type="User", password="def", member_of_groups=[test_group])
    await core_acc.save(db=db)

    # Delete CoreStandardGroup. This should also (correctly) update rels to CoreGenericAccount and CoreAccount
    # but we will override them afterward to reproduce corrupted state.
    await test_group.delete(db=db)

    # Make relationship between CoreAccount <> group_member <> CoreStandardGroup active while it should have been deleted.
    # and make the group_member <> CoreAccount edge part on global branch

    query = """
    MATCH (new_core_acc: CoreAccount)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(:AttributeValue {value: "core_acc"})
    MATCH (new_core_acc)-[r1:IS_RELATED]-(group_member: Relationship)-[r2:IS_RELATED]-(test_group: CoreStandardGroup)
    MATCH (new_core_acc)-[active_r1]-(group_member)
    WHERE active_r1.status = 'active'
    MATCH (new_core_acc)-[deleted_r1]-(group_member)
    WHERE deleted_r1.status = 'deleted'
    MATCH (test_group)-[active_r2]-(group_member)
    WHERE active_r2.status = 'active'
    MATCH (test_group)-[deleted_r2]-(group_member)
    WHERE deleted_r2.status = 'deleted'

    DELETE deleted_r1
    REMOVE active_r1.to
    SET active_r1.branch = '-global-'

    DELETE deleted_r2
    REMOVE active_r2.to

    return new_core_acc, group_member, test_group
    """

    await db.execute_query(query=query, name="query_1")

    # Create the old CoreAccount object - not inheriting from GenericAccount -
    # sharing same attributes / relationships than above CoreAccount

    query_2 = """
    // Match the existing CoreAccount node with the specified attributes
    MATCH (new_core_acc:CoreAccount)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(:AttributeValue {value: "core_acc"})

    // Create the new CoreAccount node with the same uuid and additional properties
    CREATE (new_node:CoreAccount:LineageOwner:LineageSource:Node {uuid: new_core_acc.uuid,
    branch_support: new_core_acc.branch_support, namespace: new_core_acc.namespace, kind: "CoreAccount"})

    WITH new_node, new_core_acc

    // Match the relationships of the existing CoreAccount node
    MATCH (new_core_acc)-[r:IS_RELATED]->(group_member:Relationship {name: "group_member"})

    // Create active branch with no to time on main branch
    CREATE (new_node)-[:IS_RELATED {branch: "main", from: "2024-02-05T15:37:07.228145Z", status: "active"}]->(group_member)

    // Create deleted branch with no to time on global branch
    CREATE (new_node)-[:IS_RELATED {branch: $global_branch, from: r.from, status: "deleted"}]->(group_member)

    // Return the new_node
    RETURN new_node;
    """

    await db.execute_query(query=query_2, name="query_2", params={"global_branch": GLOBAL_BRANCH_NAME})

    # Make sure migration executes without error, and that we can query accounts afterwards.
    # Note generated corrupted state does not trigger IFC-1204 bug,
    # but a manual test confirmed migration solves this issue.

    migration = Migration019()
    await migration.execute(db=db, at=Timestamp())
    await migration.validate_migration(db=db)

    # Verify edges are correct, ie:
    # - 2 edges on main branch between old CoreAccount and group_member, 1 active with from/to set, 1 deleted
    # - 2 edges on main branch between new CoreAccount and group_member, 1 active with from/to set, 1 deleted
    # - 2 edges on main branch between CoreStandardGroup and group_member, 1 active with from/to set, 1 deleted

    check_deleted_edges_query = """
    MATCH (n {uuid: $uuid})-[r1:IS_RELATED]-(rel:Relationship {name: 'group_member'})
    WHERE r1.branch = 'main'
    WITH n, rel, COLLECT(r1) AS edges
    WITH
        edges,
        SIZE(edges) AS edgeCount,
        [e IN edges WHERE e.status = 'active' AND e.from IS NOT NULL AND e.to IS NOT NULL] AS activeEdges,
        [e IN edges WHERE e.status = 'deleted'] AS deletedEdges
    WHERE edgeCount = 2 AND SIZE(activeEdges) = 1 AND SIZE(deletedEdges) = 1 AND activeEdges[0].to = deletedEdges[0].from
    RETURN 'Old CoreAccount edges are correct' AS result
    """

    core_accounts_results = await db.execute_query(
        query=check_deleted_edges_query, name="check_deleted_edges_query", params={"uuid": core_acc.id}
    )
    assert len(core_accounts_results) == 2

    group_results = await db.execute_query(
        query=check_deleted_edges_query, name="check_deleted_edges_query", params={"uuid": test_group.id}
    )
    assert len(group_results) == 1

    # Additional sanity checks
    await validate_node_relationships(node=test_group, branch=default_branch, db=db)
    await validate_node_relationships(node=test_group, branch=registry.get_global_branch(), db=db)


async def test_incorrectly_deleted_aware_nodes_and_relationship(
    db: InfrahubDatabase, branch, car_person_schema_unregistered
) -> None:
    """
    Reproduce a state where a branch aware node would have been incorrectly deleted, this node being
    connected to another node through a branch aware relationship.
    """

    registry.schema.register_schema(schema=car_person_schema_unregistered, branch=branch.name)

    john = await Node.init(schema="TestPerson", db=db, branch=branch)
    await john.new(db=db, name="John")
    await john.save(db=db)

    car = await Node.init(schema="TestCar", db=db, branch=branch)
    await car.new(db=db, name="test-car", owner=john)
    await car.save(db=db)

    # Reproduce corrupted state by only deleting is_part_of edge

    delete_only_is_part_of_query = """
    MATCH (car:TestCar {uuid: $uuid})-[r:IS_PART_OF {status: "active"}]-(root:Root)
    SET r.to = $at
    CREATE (car)-[:IS_PART_OF {status: "deleted", from: $at, branch: $branch, branch_level: 2}]->(root)

    """

    await db.execute_query(
        query=delete_only_is_part_of_query,
        name="delete_only_is_part_of_query",
        params={"uuid": car.id, "at": current_timestamp(), "branch": branch.name},
    )

    migration = Migration019()
    await migration.execute(db=db, at=Timestamp())
    await migration.validate_migration(db=db)

    await validate_node_relationships(node=car, branch=branch, db=db)


async def test_incorrectly_deleted_agnostic_node(
    db: InfrahubDatabase, branch, car_person_branch_agnostic_schema
) -> None:
    """
    Reproduce a state where a branch agnostic node would have been incorrectly deleted, this node being
    connected to another node through 2 relationships, both aware and agnostic.
    """

    # await load_schema(db, schema=CAR_SCHEMA)
    registry.schema.register_schema(schema=SchemaRoot(**car_person_branch_agnostic_schema), branch=branch.name)

    aware_person = await Node.init(schema="TestPerson", db=db, branch=branch)
    await aware_person.new(db=db, name="John")
    await aware_person.save(db=db)

    agnostic_car = await Node.init(schema="TestCar", db=db, branch=branch)
    await agnostic_car.new(db=db, name="test-car", agnostic_owner=aware_person, aware_owner=aware_person)
    await agnostic_car.save(db=db)

    # Reproduce corrupted state by only deleting is_part_of edge

    delete_only_is_part_of_query = """
    MATCH (car:TestCar {uuid: $uuid})-[r:IS_PART_OF {status: "active"}]-(root:Root)
    SET r.to = $at
    CREATE (car)-[:IS_PART_OF {status: "deleted", from: $at, branch: $global_branch, branch_level: 1}]->(root)
    """

    await db.execute_query(
        query=delete_only_is_part_of_query,
        name="delete_only_is_part_of_query",
        params={"uuid": agnostic_car.id, "at": current_timestamp(), "global_branch": GLOBAL_BRANCH_NAME},
    )

    migration = Migration019()
    await migration.execute(db=db, at=Timestamp())
    await migration.validate_migration(db=db)

    await validate_node_relationships(node=agnostic_car, branch=branch, db=db)
    await validate_node_relationships(node=agnostic_car, branch=registry.get_global_branch(), db=db)


async def test_incorrectly_deleted_aware_node(db: InfrahubDatabase, branch, car_person_branch_agnostic_schema) -> None:
    """
    Reproduce a state where a branch agnostic node would have been incorrectly deleted, this node being
    connected to another node through 2 relationships, both aware and agnostic.
    Note that, after deleting an aware node, agnostic edges of this node will not be deleted.
    """

    registry.schema.register_schema(schema=SchemaRoot(**car_person_branch_agnostic_schema), branch=branch.name)

    aware_person = await Node.init(schema="TestPerson", db=db, branch=branch)
    await aware_person.new(db=db, name="John")
    await aware_person.save(db=db)

    agnostic_car = await Node.init(schema="TestCar", db=db, branch=branch)
    await agnostic_car.new(db=db, name="test-car", agnostic_owner=aware_person, aware_owner=aware_person)
    await agnostic_car.save(db=db)

    # Reproduce corrupted state by only deleting is_part_of edge

    delete_only_is_part_of_query = """
    MATCH (person:TestPerson {uuid: $uuid})-[r:IS_PART_OF {status: "active"}]-(root:Root)
    SET r.to = $at
    CREATE (person)-[:IS_PART_OF {status: "deleted", from: $at, branch: $branch, branch_level: 1}]->(root)
    """

    await db.execute_query(
        query=delete_only_is_part_of_query,
        name="delete_only_is_part_of_query",
        params={"uuid": aware_person.id, "at": current_timestamp(), "branch": branch.name},
    )

    migration = Migration019()
    await migration.execute(db=db, at=Timestamp())
    await migration.validate_migration(db=db)

    await validate_node_relationships(node=aware_person, branch=branch, db=db)
    await validate_node_relationships(node=aware_person, branch=registry.get_global_branch(), db=db)
