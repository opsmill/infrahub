from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.migrations.graph import MIGRATIONS

from .exceptions import MigrationFailureError
from .shared import MigrationRequiringRebase

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class MigrationRunner:
    def __init__(self, branch: Branch) -> None:
        if branch.name in (registry.default_branch, GLOBAL_BRANCH_NAME):
            raise ValueError("MigrationRunner cannot be used to apply migration on default branches")

        self.branch = branch
        self.applicable_migrations = self._get_applicable_migrations()

    def _get_applicable_migrations(self) -> Sequence[MigrationRequiringRebase]:
        applicable_migrations = []
        for migration_class in [m for m in MIGRATIONS if issubclass(m, MigrationRequiringRebase)]:
            migration = migration_class.init()
            if self.branch.graph_version and self.branch.graph_version > migration.minimum_version:
                continue
            applicable_migrations.append(migration)

        return applicable_migrations

    def has_migrations(self) -> bool:
        return bool(self.applicable_migrations)

    async def run(self, db: InfrahubDatabase) -> None:
        if not self.has_migrations():
            return

        for migration in self.applicable_migrations:
            execution_result = await migration.execute_against_branch(db=db, branch=self.branch)
            validation_result = None

            if execution_result.success:
                validation_result = await migration.validate_migration(db=db)

            if not execution_result.success or (validation_result and not validation_result.success):
                if execution_result.errors:
                    raise MigrationFailureError(errors=execution_result.errors)

                if validation_result and not validation_result.success:
                    raise MigrationFailureError(errors=validation_result.errors)
