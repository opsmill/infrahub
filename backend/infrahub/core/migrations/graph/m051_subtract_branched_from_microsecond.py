from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationResult
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class Migration051(ArbitraryMigration):
    name: str = "051_subtract_branched_from_microsecond"
    minimum_version: int = 50

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()

        branches = await Branch.get_list(db=db)

        for branch in branches:
            if branch.is_default or branch.is_global:
                continue

            if not branch.branched_from:
                continue

            original_ts = Timestamp(branch.branched_from)
            new_ts = original_ts.subtract(microseconds=1)
            branch.branched_from = new_ts.to_string()

            await branch.save(db=db)

        return result
