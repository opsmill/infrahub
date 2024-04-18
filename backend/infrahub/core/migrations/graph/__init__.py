from __future__ import annotations

from typing import TYPE_CHECKING, List, Sequence

from .m001_add_version_to_graph import Migration001
from .m002_attribute_is_default import Migration002

if TYPE_CHECKING:
    from infrahub.core.root import Root

    from ..shared import GraphMigration

MIGRATIONS: List[GraphMigration] = [
    Migration001,
    Migration002,
]


async def get_graph_migrations(root: Root) -> Sequence[GraphMigration]:
    applicable_migrations = []
    for migration_class in MIGRATIONS:
        migration = migration_class.init()
        if root.graph_version > migration.minimum_version:
            continue
        applicable_migrations.append(migration)

    return applicable_migrations
