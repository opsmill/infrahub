from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.migrations.shared import MigrationResult, MigrationSimple

if TYPE_CHECKING:
    from infrahub.core.migrations.shared import MigrationInput


class Migration066(MigrationSimple):
    """Add CoreTransformAI schema to the internal schema."""

    name: str = "066_add_transform_ai"
    minimum_version: int = 65

    async def validate_migration(self, input: MigrationInput) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, input: MigrationInput) -> MigrationResult:  # noqa: ARG002
        """No-op migration.

        The CoreTransformAI schema is automatically added to the internal schema
        when it's registered in core/schema/definitions/core/__init__.py.
        The schema loading process will handle creating the necessary graph nodes.
        """
        return MigrationResult()
