from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

import ujson

from infrahub.core.attribute import MAX_STRING_LENGTH
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult, get_migration_console

if TYPE_CHECKING:
    from neo4j import Record

    from infrahub.database import InfrahubDatabase

console = get_migration_console()

FETCH_HFID_VALUES_QUERY = """
MATCH (attr:Attribute {name: "human_friendly_id"})-[:HAS_VALUE]->(av:AttributeValue)
WHERE av.value IS NOT NULL
RETURN DISTINCT elementId(av) AS element_id, av.value AS value, av:AttributeValueIndexed AS is_indexed
ORDER BY element_id
SKIP $offset LIMIT $limit
"""

NORMALIZE_VALUES_QUERY = """
UNWIND $updates AS update
MATCH (attr:Attribute {name: "human_friendly_id"})-[old_r:HAS_VALUE]->(old_av)
WHERE elementId(old_av) = update.element_id
CALL (update, attr, old_r, old_av) {
    MERGE (new_av:AttributeValue {value: update.new_value, is_default: old_av.is_default})
    WITH attr, old_r, new_av
    LIMIT 1
    CREATE (attr)-[new_r:HAS_VALUE]->(new_av)
    SET new_r = properties(old_r)
    DELETE old_r
} IN TRANSACTIONS OF 500 ROWS
"""

INDEX_EXCLUSIVE_HFID_VALUES_QUERY = """
MATCH (attr:Attribute {name: "human_friendly_id"})-[:HAS_VALUE]->(av:AttributeValue)
WHERE NOT av:AttributeValueIndexed
    AND size(av.value) < $max_length
    AND NOT EXISTS {
        MATCH (other:Attribute)-[:HAS_VALUE]->(av)
        WHERE other.name <> "human_friendly_id"
    }
WITH DISTINCT av
CALL (av) {
    SET av:AttributeValueIndexed
} IN TRANSACTIONS OF 1000 ROWS
"""

INDEX_SHARED_HFID_VALUES_QUERY = """
MATCH (attr:Attribute {name: "human_friendly_id"})-[old_r:HAS_VALUE]->(av:AttributeValue)
WHERE NOT av:AttributeValueIndexed
    AND size(av.value) < $max_length
    AND EXISTS {
        MATCH (other:Attribute)-[:HAS_VALUE]->(av)
        WHERE other.name <> "human_friendly_id"
    }
CALL (attr, old_r, av) {
    MERGE (new_av:AttributeValue:AttributeValueIndexed {value: av.value, is_default: av.is_default})
    WITH attr, old_r, new_av
    LIMIT 1
    CREATE (attr)-[new_r:HAS_VALUE]->(new_av)
    SET new_r = properties(old_r)
    DELETE old_r
} IN TRANSACTIONS OF 500 ROWS
"""


class NormalizeUpdate(TypedDict):
    element_id: str
    new_value: str


def _needs_normalization(record: Record) -> NormalizeUpdate | None:
    """Determine if an HFID value needs normalization to all-strings."""
    raw_value = record.get("value")

    if not isinstance(raw_value, str):
        return None

    try:
        parsed = ujson.loads(raw_value)
    except (ujson.JSONDecodeError, ValueError):
        return None

    if not isinstance(parsed, list):
        return None

    normalized = [str(item) for item in parsed]
    new_value = ujson.dumps(normalized)

    if new_value == raw_value:
        return None

    return NormalizeUpdate(element_id=record.get("element_id"), new_value=new_value)


class Migration070(ArbitraryMigration):
    """Index HFID attribute values and normalize them to list[str].

    Existing HFID values may contain non-string JSON elements (e.g., ints)
    from the old compute behavior. This migration normalizes all elements
    to strings and adds the AttributeValueIndexed label for values within
    the Neo4j index size limit.
    """

    name: str = "070_index_hfid_values"
    minimum_version: int = 69
    update_batch_size: int = 1000

    async def _normalize_hfid_values(self, db: InfrahubDatabase) -> None:
        """Normalize HFID values to all-strings, in batches.

        Creates new AttributeValue nodes and transfers HAS_VALUE edges
        to avoid corrupting shared AttributeValue nodes.
        """
        offset = 0
        total_normalized = 0

        while True:
            results = await db.execute_query(
                query=FETCH_HFID_VALUES_QUERY, params={"offset": offset, "limit": self.update_batch_size}
            )

            if not results:
                break

            updates: list[NormalizeUpdate] = []
            for record in results:
                update = _needs_normalization(record=record)
                if update:
                    updates.append(update)

            if updates:
                await db.execute_query(query=NORMALIZE_VALUES_QUERY, params={"updates": updates})
                total_normalized += len(updates)

            offset += self.update_batch_size

        if total_normalized:
            console.log(f"Normalized {total_normalized} HFID value(s) to all-string format")

    async def _index_hfid_values(self, db: InfrahubDatabase) -> None:
        """Add AttributeValueIndexed label to HFID values within the index size limit.

        Exclusive values (only used by HFID attributes) get the label added in-place.
        Shared values (also used by non-HFID attributes) get a new AttributeValueIndexed
        node created, with HAS_VALUE edges transferred from the old node.
        """
        await db.execute_query(query=INDEX_EXCLUSIVE_HFID_VALUES_QUERY, params={"max_length": MAX_STRING_LENGTH})
        await db.execute_query(query=INDEX_SHARED_HFID_VALUES_QUERY, params={"max_length": MAX_STRING_LENGTH})
        console.log("Added AttributeValueIndexed label to HFID values")

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        try:
            await self._normalize_hfid_values(db=db)
            await self._index_hfid_values(db=db)
        except Exception as exc:
            return MigrationResult(errors=[str(exc)])

        return MigrationResult()
