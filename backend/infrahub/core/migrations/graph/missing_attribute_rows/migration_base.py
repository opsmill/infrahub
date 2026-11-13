from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.migrations.graph.load_schema_branch import get_or_load_schema_branch
from infrahub.core.migrations.shared import (
    MigrationInput,
    MigrationRequiringRebase,
    MigrationResult,
    get_migration_console,
)

from .healer import MissingAttributeRowHealer, ensure_runtime_context

if TYPE_CHECKING:
    from rich.console import Console

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from .repairers import MissingRowRepairer


class MissingAttributeRowsMigration(MigrationRequiringRebase):
    """Backfill the generic-inherited attribute rows a family of attributes is missing.

    A subclass names the repairers, and with them the attributes it covers. The default
    branch is repaired at upgrade; every other branch is repaired by its post-upgrade
    rebase, after which it also sees the default branch's rows. The run is idempotent
    and performs zero writes on healthy data. Validation re-runs the damage detection
    on the default branch and reports per-kind errors for any remaining damaged pair,
    which fails the upgrade; the per-branch pass re-validates its own scope before
    returning.
    """

    repair_batch_size: int = 1000

    def _repairers(self, db: InfrahubDatabase, console: Console) -> list[MissingRowRepairer]:
        raise NotImplementedError()

    def _healer(self, db: InfrahubDatabase, console: Console) -> MissingAttributeRowHealer:
        return MissingAttributeRowHealer(db=db, console=console, repairers=self._repairers(db=db, console=console))

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        result = MigrationResult()

        try:
            await ensure_runtime_context(db=db)
            default_branch = await registry.get_branch(db=db, branch=registry.default_branch)
            result = await self._healer(db=db, console=migration_input.console).heal(
                branch=default_branch, at=migration_input.at, user_id=migration_input.user_id
            )
        except Exception as exc:  # noqa: BLE001 - a repair failure is reported, never raised out of a migration
            migration_input.console.print_exception()
            result.errors.append(f"{type(exc).__name__}: {exc}")

        return result

    async def execute_against_branch(self, migration_input: MigrationInput, branch: Branch) -> MigrationResult:
        """Heal the branch's damage, assuming the branch was rebased first.

        The audit is restricted to kinds whose inherited attributes go beyond the
        default branch's schema: missing rows on a branch can only stem from
        inheritance the branch's own schema added, and post-rebase everything else
        is already covered by the default branch's rows. The branch is re-audited
        before returning, because the upgrade-time validation only covers the
        default branch.
        """
        db = migration_input.db
        result = MigrationResult()

        try:
            await ensure_runtime_context(db=db)
            if branch.name not in registry.branch:
                registry.branch[branch.name] = branch
            default_branch = await registry.get_branch(db=db, branch=registry.default_branch)
            baseline_schema = await get_or_load_schema_branch(db=db, branch=default_branch)
            healer = self._healer(db=db, console=migration_input.console)
            result = await healer.heal(
                branch=branch, at=migration_input.at, user_id=migration_input.user_id, baseline_schema=baseline_schema
            )
            if result.errors:
                return result
            result.errors.extend(await healer.detect_remaining_damage(branch=branch, baseline_schema=baseline_schema))
        except Exception as exc:  # noqa: BLE001 - a repair failure is reported, never raised out of a migration
            migration_input.console.print_exception()
            result.errors.append(f"{type(exc).__name__}: {exc}")

        return result

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        """Audit the default branch; run after execute() at upgrade and after every per-branch pass."""
        result = MigrationResult()
        console = get_migration_console()

        try:
            await ensure_runtime_context(db=db)
            default_branch = await registry.get_branch(db=db, branch=registry.default_branch)
            result.errors.extend(
                await self._healer(db=db, console=console).detect_remaining_damage(branch=default_branch)
            )
        except Exception as exc:  # noqa: BLE001 - a repair failure is reported, never raised out of a migration
            console.print_exception()
            result.errors.append(f"{type(exc).__name__}: {exc}")

        return result
