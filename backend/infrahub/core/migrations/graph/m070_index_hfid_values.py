from __future__ import annotations

from typing import TYPE_CHECKING, Any

import ujson

from infrahub.core.attribute import MAX_STRING_LENGTH
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult, get_migration_console

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

console = get_migration_console()


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

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        try:
            await self._normalize_and_index_hfid_values(db=db)
        except Exception as exc:
            return MigrationResult(errors=[str(exc)])

        return MigrationResult()

    async def _normalize_and_index_hfid_values(self, db: InfrahubDatabase) -> None:
        """Normalize HFID values to all-strings and add the indexed label, in batches."""
        offset = 0
        total_normalized = 0
        total_indexed = 0

        while True:
            fetch_query = """
            MATCH (attr:Attribute {name: "human_friendly_id"})-[:HAS_VALUE]->(av:AttributeValue)
            WHERE av.value IS NOT NULL
            RETURN elementId(av) AS element_id, av.value AS value, av:AttributeValueIndexed AS is_indexed
            ORDER BY elementId(av)
            SKIP $offset LIMIT $limit
            """
            results = await db.execute_query(
                query=fetch_query, params={"offset": offset, "limit": self.update_batch_size}
            )

            if not results:
                break

            updates: list[dict[str, Any]] = []
            for record in results:
                raw_value = record.get("value")
                is_indexed = record.get("is_indexed")

                if not isinstance(raw_value, str):
                    continue

                try:
                    parsed = ujson.loads(raw_value)
                except (ujson.JSONDecodeError, ValueError):
                    continue

                if not isinstance(parsed, list):
                    continue

                normalized = [str(item) for item in parsed]
                new_value = ujson.dumps(normalized)
                needs_normalize = new_value != raw_value
                needs_index = not is_indexed and 3 + len(new_value.encode("utf-8")) < MAX_STRING_LENGTH

                if needs_normalize or needs_index:
                    updates.append(
                        {"element_id": record.get("element_id"), "new_value": new_value, "add_index": needs_index}
                    )
                    if needs_normalize:
                        total_normalized += 1
                    if needs_index:
                        total_indexed += 1

            if updates:
                update_query = """
                UNWIND $updates AS update
                CALL (update) {
                    MATCH (av) WHERE elementId(av) = update.element_id
                    SET av.value = update.new_value
                    WITH av, update
                    WHERE update.add_index = true
                    SET av:AttributeValueIndexed
                } IN TRANSACTIONS OF 500 ROWS
                """
                await db.execute_query(query=update_query, params={"updates": updates})

            offset += self.update_batch_size

        if total_normalized:
            console.log(f"Normalized {total_normalized} HFID value(s) to all-string format")
        if total_indexed:
            console.log(f"Added AttributeValueIndexed label to {total_indexed} HFID value(s)")
