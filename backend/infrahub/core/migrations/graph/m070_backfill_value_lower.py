from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.migrations.shared import ArbitraryMigration, MigrationResult

if TYPE_CHECKING:
    from infrahub.core.migrations.shared import MigrationInput
    from infrahub.database import InfrahubDatabase


class Migration070(ArbitraryMigration):
    """Backfill value_lower on all existing AttributeValueIndexed nodes for case-insensitive search."""

    name: str = "070_backfill_value_lower"
    minimum_version: int = 69

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        await db.execute_query(
            query="""
            MATCH (av:AttributeValueIndexed)
            WHERE av.value_lower IS NULL
            CALL (av) {
                SET av.value_lower = toLower(toString(av.value))
            } IN TRANSACTIONS
            """,
            name="backfill_value_lower",
        )
        return MigrationResult()
