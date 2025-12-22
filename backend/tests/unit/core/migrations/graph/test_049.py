from infrahub.core.migrations.graph import Migration049
from infrahub.core.timestamp import current_timestamp
from infrahub.database import InfrahubDatabase


async def test_migration_049(db: InfrahubDatabase, default_branch, person_john_main, car_accord_main) -> None:
    count_is_visible_relationship_query = """
    MATCH ()-[rel:IS_VISIBLE]-()
    RETURN count(*) AS is_visible_count;
    """
    is_visible_count = await db.execute_query(query=count_is_visible_relationship_query)
    assert is_visible_count[0].get("is_visible_count") == 0

    car_name_attr = car_accord_main.get_attribute("name")
    person_name_attr = person_john_main.get_attribute("name")

    add_is_visible_relationship_query = """
    MERGE (bool_true:Boolean { value: true })

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

    is_visible_count = await db.execute_query(query=count_is_visible_relationship_query)
    assert is_visible_count[0].get("is_visible_count") == 4

    migration = Migration049()
    await migration.execute(db=db)
    result = await migration.validate_migration(db=db)
    assert result.success

    is_visible_count = await db.execute_query(query=count_is_visible_relationship_query)
    assert is_visible_count[0].get("is_visible_count") == 0