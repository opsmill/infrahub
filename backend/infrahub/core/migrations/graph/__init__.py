from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from .discovery import discover_migrations

if TYPE_CHECKING:
    from ..shared import BaseMigration


MIGRATIONS: list[type[BaseMigration]] = discover_migrations()


async def get_graph_migrations(current_graph_version: int) -> Sequence[BaseMigration]:
    applicable_migrations = []
    for migration_class in MIGRATIONS:
        migration = migration_class.init()
        if current_graph_version > migration.minimum_version:
            continue
        applicable_migrations.append(migration)

    return applicable_migrations


def get_migration_by_number(migration_number: int | str) -> MigrationTypes:
    # Convert to string and pad with zeros if needed
    try:
        num = int(migration_number)
        migration_str = f"{num:03d}"
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid migration number: {migration_number}") from exc

    migration_name = f"Migration{migration_str}"

    # Find the migration in the MIGRATIONS list
    for migration_class in MIGRATIONS:
        if migration_class.__name__ == migration_name:
            return migration_class.init()

    raise ValueError(f"Migration {migration_number} not found")
