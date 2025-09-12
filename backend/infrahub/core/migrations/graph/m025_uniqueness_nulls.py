from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.log import get_logger

from ..shared import InternalSchemaMigration, SchemaMigration
from .m018_uniqueness_nulls import validate_nulls_in_uniqueness_constraints

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class Migration025(InternalSchemaMigration):
    name: str = "025_validate_nulls_in_uniqueness_constraints"
    minimum_version: int = 24
    migrations: Sequence[SchemaMigration] = []

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        return await validate_nulls_in_uniqueness_constraints(db=db)
