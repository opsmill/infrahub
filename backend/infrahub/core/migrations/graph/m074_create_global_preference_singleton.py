from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, InfrahubKind
from infrahub.core.initialization import get_root_node
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.shared import (
    ArbitraryMigration,
    MigrationInput,
    MigrationResult,
)
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.definitions.core.preference import core_global_preference
from infrahub.permissions.globals import get_or_create_global_permission

from .load_schema_branch import get_or_load_schema_branch

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class Migration074(ArbitraryMigration):
    """Create the manage_global_preferences permission and the CoreGlobalPreference singleton.

    New installs get both nodes from first_time_initialization(); this migration idempotently
    backfills existing installs.
    """

    name: str = "074_create_global_preference_singleton"
    description: str = "Create the manage_global_preferences permission and the CoreGlobalPreference singleton"
    minimum_version: int = 73

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        result = MigrationResult()

        root_node = await get_root_node(db=db, initialize=False)
        default_branch = await Branch.get_by_name(db=db, name=root_node.default_branch)
        schema_branch = await get_or_load_schema_branch(db=db, branch=default_branch)

        # The CoreGlobalPreference schema node ships in the same release as this migration:
        # on an existing install the database schema does not contain it yet when migrations
        # run (the core schema update happens afterwards), so load it in memory first.
        if not schema_branch.has(name=InfrahubKind.GLOBALPREFERENCE):
            schema_branch.load_schema(schema=SchemaRoot(nodes=[core_global_preference.model_copy(deep=True)]))
            schema_branch.process()

        try:
            await get_or_create_global_permission(db=db, permission=GlobalPermissions.MANAGE_GLOBAL_PREFERENCES)

            existing = await NodeManager.query(
                db=db, schema=InfrahubKind.GLOBALPREFERENCE, branch=default_branch, limit=1
            )
            if not existing:
                preference = await Node.init(db=db, schema=InfrahubKind.GLOBALPREFERENCE, branch=default_branch)
                await preference.new(db=db)
                await preference.save(db=db)
        except Exception as exc:
            result.errors.append(str(exc))

        return result
