"""Change the schema of a branch the way a schema load does and run the migrations the change gives."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData
from infrahub.core.migrations.schema.runner import SchemaMigrationRunner
from infrahub.core.migrations.schema.scheduler import MigrationScheduler
from infrahub.core.migrations.schema.tasks import MAX_CONCURRENT_MIGRATION_GROUPS, TaskSchemaPathMigrator
from infrahub.core.schema_change.migration_recorder import NoRecordMigrationRecorder
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.schema_change.migration_recorder import MigrationRecorder
    from infrahub.database import InfrahubDatabase


def build_migration_runner(db: InfrahubDatabase, recorder: MigrationRecorder) -> SchemaMigrationRunner:
    """Build the runner a schema load uses, with its migration classes, its concurrency limit and the recorder."""
    return SchemaMigrationRunner(
        scheduler=MigrationScheduler(migration_classes=MIGRATION_MAP),
        migrator=TaskSchemaPathMigrator(database=db),
        recorder=recorder,
        max_concurrent_groups=MAX_CONCURRENT_MIGRATION_GROUPS,
        log=logging.getLogger(__name__),
    )


async def register_candidate(db: InfrahubDatabase, branch: Branch, candidate: SchemaBranch) -> None:
    """Store the candidate schema on the branch the way a schema load does before its migrations run."""
    candidate.process()
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)
    branch.update_schema_hash()
    await branch.save(db=db)


async def store_schema_ids(db: InfrahubDatabase, default_branch: Branch) -> None:
    """Store the registered schema, so that its elements get the IDs that let the diff see a rename."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    await registry.schema.load_schema_to_db(schema=schema, branch=default_branch, db=db, at=Timestamp())


async def load_schema_change(
    db: InfrahubDatabase,
    branch: Branch,
    change_schema: Callable[[SchemaBranch], None],
    expected_migration_names: list[str],
) -> Timestamp:
    """Change the schema of the branch as a schema load does, run the migrations the change gives and return their timestamp."""
    previous_schema = registry.schema.get_schema_branch(name=branch.name).duplicate()
    candidate = previous_schema.duplicate()
    change_schema(candidate)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    validation = previous_schema.validate_update(other=candidate, diff=previous_schema.diff(other=candidate))
    assert sorted(migration.migration_name for migration in validation.migrations) == expected_migration_names

    at = Timestamp()
    errors = await build_migration_runner(db=db, recorder=NoRecordMigrationRecorder()).run(
        data=SchemaApplyMigrationData(
            branch=branch,
            previous_schema=previous_schema,
            new_schema=candidate,
            migrations=validation.migrations,
            at=at,
        )
    )

    assert errors == []
    return at
