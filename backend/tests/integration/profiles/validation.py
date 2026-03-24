from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import OBJECT_TEMPLATE_RELATIONSHIP_NAME, PROFILES_RELATIONSHIP_NAME

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

VIRTUAL_RELATIONSHIP_NAMES = (PROFILES_RELATIONSHIP_NAME, OBJECT_TEMPLATE_RELATIONSHIP_NAME)


async def assert_no_virtual_schema_relationships_in_db(db: InfrahubDatabase) -> None:
    """Assert that no SchemaRelationship nodes with the given name exist in the database.

    Virtual SchemaRelationships (only exist in-memory during SchemaBranch.process)
    should never be persisted to the database.
    Finding any in the DB indicates a bug in the schema persistence layer.
    """
    query = """
    MATCH (sr:SchemaRelationship)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(av:AttributeValue)
    WHERE av.value IN $rel_names
    RETURN count(sr) AS cnt
    """
    result = await db.execute_query(query=query, params={"rel_names": list(VIRTUAL_RELATIONSHIP_NAMES)})
    count = result[0][0]
    assert count == 0, (
        f"Found {count} virtual SchemaRelationship nodes in the database. "
        f"The {VIRTUAL_RELATIONSHIP_NAMES} relationships are virtual and should never be persisted."
    )
