from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

import ujson

from infrahub.core.attribute import MAX_STRING_LENGTH
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult, get_migration_console

if TYPE_CHECKING:
    from neo4j import Record

    from infrahub.database import InfrahubDatabase

console = get_migration_console()

# Paginate over the HFID attributes, not the value nodes. The writes move edges and
# delete value nodes, so paging over the values would mutate the set mid-scan and skip
# rows; the attribute nodes are never touched, so their order stays stable.
FETCH_HFID_VALUES_QUERY = """
MATCH (attr:Attribute {name: "human_friendly_id"})
WITH attr ORDER BY elementId(attr) SKIP $offset LIMIT $limit
OPTIONAL MATCH (attr)-[:HAS_VALUE]->(av:AttributeValue)
WHERE av.value IS NOT NULL
RETURN elementId(av) AS element_id, av.value AS value, av:AttributeValueIndexed AS is_indexed
"""

# Move the HFID edges onto a normalized node, then drop the old node once no edge
# references it. The per-row CALL runs the move and orphan check together.
NORMALIZE_INDEXED_QUERY = """
UNWIND $updates AS update
MATCH (attr:Attribute {name: "human_friendly_id"})-[old_r:HAS_VALUE]->(old_av:AttributeValue)
WHERE elementId(old_av) = update.element_id
CALL (attr, old_r, old_av, update) {
    MERGE (new_av:AttributeValue:AttributeValueIndexed {value: update.new_value, is_default: old_av.is_default})
    WITH attr, old_r, old_av, new_av
    LIMIT 1
    CREATE (attr)-[new_r:HAS_VALUE]->(new_av)
    SET new_r = properties(old_r)
    DELETE old_r
    WITH old_av
    WHERE NOT (old_av)--()
    DELETE old_av
} IN TRANSACTIONS OF 500 ROWS
"""

NORMALIZE_PLAIN_QUERY = """
UNWIND $updates AS update
MATCH (attr:Attribute {name: "human_friendly_id"})-[old_r:HAS_VALUE]->(old_av:AttributeValue)
WHERE elementId(old_av) = update.element_id
CALL (attr, old_r, old_av, update) {
    MERGE (new_av:AttributeValue {value: update.new_value, is_default: old_av.is_default})
    WITH attr, old_r, old_av, new_av
    LIMIT 1
    CREATE (attr)-[new_r:HAS_VALUE]->(new_av)
    SET new_r = properties(old_r)
    DELETE old_r
    WITH old_av
    WHERE NOT (old_av)--()
    DELETE old_av
} IN TRANSACTIONS OF 500 ROWS
"""


class NormalizeUpdate(TypedDict):
    element_id: str
    new_value: str


def _needs_normalization(record: Record) -> NormalizeUpdate | None:
    """Return the update needed to turn an HFID value into an all-strings list, or None."""
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


class Migration074(ArbitraryMigration):
    """Repair HFID values that were stored with non-string elements and indexed.

    Normalizes them to all-string lists, keeps the indexed label when the value
    still fits the index size limit, and removes the old value node.
    """

    name: str = "074_normalize_indexed_hfid_values"
    description: str = "Normalize HFID values with non-string elements that the indexing migration left behind."
    minimum_version: int = 73
    update_batch_size: int = 1000

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def _normalize_hfid_values(self, db: InfrahubDatabase) -> None:
        """Normalize HFID values to all-strings, one batch at a time.

        Each batch is written before the next is read. This is safe because the
        pagination anchors on the HFID attributes, which the writes never touch.
        """
        offset = 0
        total = 0

        while True:
            results = await db.execute_query(
                query=FETCH_HFID_VALUES_QUERY, params={"offset": offset, "limit": self.update_batch_size}
            )

            if not results:
                break

            indexed_updates: dict[str, NormalizeUpdate] = {}
            plain_updates: dict[str, NormalizeUpdate] = {}
            for record in results:
                update = _needs_normalization(record=record)
                if update is None:
                    continue
                # Keep the indexed label only when the normalized value still fits the index,
                # using the same byte-length check the runtime applies before indexing.
                if record.get("is_indexed") and 3 + len(update["new_value"].encode("utf-8")) < MAX_STRING_LENGTH:
                    indexed_updates[update["element_id"]] = update
                else:
                    plain_updates[update["element_id"]] = update

            if indexed_updates:
                await db.execute_query(
                    query=NORMALIZE_INDEXED_QUERY, params={"updates": list(indexed_updates.values())}
                )
            if plain_updates:
                await db.execute_query(query=NORMALIZE_PLAIN_QUERY, params={"updates": list(plain_updates.values())})
            total += len(indexed_updates) + len(plain_updates)

            offset += self.update_batch_size

        if total:
            console.log(f"Normalized {total} HFID value(s) to all-string format")

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        try:
            await self._normalize_hfid_values(db=db)
        except Exception as exc:
            return MigrationResult(errors=[str(exc)])

        return MigrationResult()
