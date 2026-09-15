from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from infrahub.core import registry
from infrahub.core.migrations.shared import MigrationInput, MigrationResult
from infrahub.core.schema.definitions.core import core_profile_schema_definition
from infrahub.core.schema.manager import SchemaManager
from infrahub.log import get_logger

from ..shared import InternalSchemaMigration, SchemaMigration
from .load_schema_branch import build_internal_schema_branch

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class Migration017(InternalSchemaMigration):
    name: str = "017_add_graph_migration"
    description: str = "N/A"
    minimum_version: int = 16
    migrations: Sequence[SchemaMigration] = []

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        """Load CoreProfile schema node in db."""
        db = migration_input.db
        at = migration_input.at
        user_id = migration_input.user_id
        default_branch = registry.get_branch_from_registry()
        manager = SchemaManager()
        manager.set_schema_branch(name=default_branch.name, schema=build_internal_schema_branch())

        db.add_schema(manager.get_schema_branch(default_branch.name))
        await manager.create_node_in_db(
            node=core_profile_schema_definition,
            db=db,
            branch=default_branch,
            user_id=user_id,
            at=at,
        )

        return MigrationResult()
