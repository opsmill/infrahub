from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.migrations.shared import MigrationResult
from infrahub.dependencies.registry import build_component_registry, get_component_registry
from infrahub.log import get_logger

from ..shared import ArbitraryMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class Migration028(ArbitraryMigration):
    """Delete all diffs because of an update to how we store diff information. All diffs will need to be recalculated"""

    name: str = "028_diff_delete_bug_fix_update"
    minimum_version: int = 27

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()

        return result

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        default_branch = registry.get_branch_from_registry()
        build_component_registry()
        component_registry = get_component_registry()
        diff_repo = await component_registry.get_component(DiffRepository, db=db, branch=default_branch)

        diff_roots = await diff_repo.get_roots_metadata()
        await diff_repo.delete_diff_roots(diff_root_uuids=[d.uuid for d in diff_roots])
        return MigrationResult()
