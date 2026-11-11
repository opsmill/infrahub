from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003  needed for pydantic
from typing import TYPE_CHECKING

from infrahub.core.migrations.shared import MigrationInput, MigrationResult
from infrahub.log import get_logger

from ..shared import InternalSchemaMigration, SchemaMigration
from .m018_uniqueness_nulls import validate_nulls_in_uniqueness_constraints

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class Migration025(InternalSchemaMigration):
    name: str = "025_validate_nulls_in_uniqueness_constraints"
    description: str = "N/A"
    minimum_version: int = 24
    migrations: Sequence[SchemaMigration] = []

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        return await validate_nulls_in_uniqueness_constraints(db=migration_input.db)
