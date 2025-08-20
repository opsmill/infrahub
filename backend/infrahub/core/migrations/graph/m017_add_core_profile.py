from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from infrahub.core import registry
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.schema.definitions.core import core_profile_schema_definition
from infrahub.core.schema.manager import SchemaManager
from infrahub.log import get_logger

from ..shared import InternalSchemaMigration, SchemaMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class Migration017(InternalSchemaMigration):
    name: str = "017_add_graph_migration"
    minimum_version: int = 16
    migrations: Sequence[SchemaMigration] = []

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()

        return result

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        """
        Load CoreProfile schema node in db.
        """
        default_branch = registry.get_branch_from_registry()
        manager = SchemaManager()
        manager.set_schema_branch(name=default_branch.name, schema=self.get_internal_schema())

        db.add_schema(manager.get_schema_branch(default_branch.name))
        await manager.load_node_to_db(node=core_profile_schema_definition, db=db, branch=default_branch)

        return MigrationResult()
