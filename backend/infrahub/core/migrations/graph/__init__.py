from __future__ import annotations

from typing import TYPE_CHECKING, Sequence, Union

from .m001_add_version_to_graph import Migration001
from .m002_attribute_is_default import Migration002
from .m003_relationship_parent_optional import Migration003
from .m004_add_attr_documentation import Migration004
from .m005_add_rel_read_only import Migration005
from .m006_add_rel_on_delete import Migration006
from .m007_add_rel_allow_override import Migration007
from .m008_add_human_friendly_id import Migration008
from .m009_add_generate_profile_attr import Migration009
from .m010_add_generate_profile_attr_generic import Migration010
from .m011_remove_profile_relationship_schema import Migration011
from .m012_add_account_generic import Migration012

if TYPE_CHECKING:
    from infrahub.core.root import Root

    from ..shared import GraphMigration, InternalSchemaMigration

MIGRATIONS: list[type[Union[GraphMigration, InternalSchemaMigration]]] = [
    Migration001,
    Migration002,
    Migration003,
    Migration004,
    Migration005,
    Migration006,
    Migration007,
    Migration008,
    Migration009,
    Migration010,
    Migration011,
    Migration012,
]


async def get_graph_migrations(root: Root) -> Sequence[Union[GraphMigration, InternalSchemaMigration]]:
    applicable_migrations = []
    for migration_class in MIGRATIONS:
        migration = migration_class.init()
        if root.graph_version > migration.minimum_version:
            continue
        applicable_migrations.append(migration)

    return applicable_migrations
