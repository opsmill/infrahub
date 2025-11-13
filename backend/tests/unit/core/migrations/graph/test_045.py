from infrahub.core.migrations.graph import Migration045
from infrahub.core.timestamp import current_timestamp
from infrahub.database import InfrahubDatabase


async def test_migration_045(db: InfrahubDatabase, default_branch, person_john_main, car_accord_main) -> None:
    count_is_visible_relationship_query = """
    MATCH (n)-[rel:IS_VISIBLE]-()
    RETURN count(DISTINCT n) AS visible_nodes_count;
    """
    visible_nodes_count = await db.execute_query(query=count_is_visible_relationship_query)
    assert visible_nodes_count[0].get("visible_nodes_count") == 0

    car_name_attr = car_accord_main.get_attribute("name")
    person_name_attr = person_john_main.get_attribute("name")

    add_is_visible_relationship_query = """
    CREATE (bool_true:Boolean { value: true })

    WITH bool_true
    MATCH (attr:Attribute {uuid: $car_name_attr_uuid})
    CREATE (attr)-[:IS_VISIBLE {
      branch: $main_branch,
      branch_level: 1,
      status: "active",
      from: $at
    }]->(bool_true)

    WITH bool_true
    MATCH (attr:Attribute {uuid: $person_name_attr_uuid})
    CREATE (attr)-[:IS_VISIBLE {
      branch: $main_branch,
      branch_level: 1,
      status: "active",
      from: $at
    }]->(bool_true);
    """
    await db.execute_query(
        query=add_is_visible_relationship_query,
        params={
            "main_branch": "main",
            "at": current_timestamp(),
            "car_name_attr_uuid": car_name_attr.id,
            "person_name_attr_uuid": person_name_attr.id,
        },
    )

    visible_nodes_count = await db.execute_query(query=count_is_visible_relationship_query)
    assert visible_nodes_count[0].get("visible_nodes_count") == 3

    migration = Migration045()
    await migration.execute(db=db)
    result = await migration.validate_migration(db=db)
    assert result.success

    visible_nodes_count = await db.execute_query(query=count_is_visible_relationship_query)
    assert visible_nodes_count[0].get("visible_nodes_count") == 0
