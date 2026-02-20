from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import PROFILES_RELATIONSHIP_NAME

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


async def assert_no_profiles_schema_relationships_in_db(db: InfrahubDatabase) -> None:
    """Assert that no SchemaRelationship nodes named 'profiles' exist in the database.

    The 'profiles' SchemaRelationship is virtual (only exists in-memory during
    SchemaBranch.process) and should never be persisted to the database.
    Finding any in the DB indicates a bug in the schema persistence layer.
    """
    query = """
    MATCH (sr:SchemaRelationship)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})
          -[:HAS_VALUE]->(av:AttributeValue {value: $rel_name})
    RETURN count(sr) AS cnt
    """
    result = await db.execute_query(query=query, params={"rel_name": PROFILES_RELATIONSHIP_NAME})
    count = result[0][0]
    assert count == 0, (
        f"Found {count} SchemaRelationship nodes named {PROFILES_RELATIONSHIP_NAME!r} in the database. "
        "The 'profiles' relationship is virtual and should never be persisted."
    )
