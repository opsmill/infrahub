from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import GlobalPermissions, InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m074_create_global_preference_singleton import Migration074
from infrahub.core.migrations.shared import MigrationInput
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def _count_permission_nodes(db: InfrahubDatabase) -> int:
    permissions = await NodeManager.query(
        db=db,
        schema=InfrahubKind.GLOBALPERMISSION,
        filters={"action__value": GlobalPermissions.MANAGE_GLOBAL_PREFERENCES.value},
    )
    return len(permissions)


async def _count_global_preference_nodes(db: InfrahubDatabase) -> int:
    preferences = await NodeManager.query(db=db, schema=InfrahubKind.GLOBALPREFERENCE)
    return len(preferences)


class TestMigration074(TestInfrahubApp):
    async def test_migration_074(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        async with db.start_session() as dbs:
            result = await Migration074().execute(migration_input=MigrationInput(db=dbs))
            assert not result.errors, result.errors

        assert await _count_permission_nodes(db=db) == 1

        preferences = await NodeManager.query(db=db, schema=InfrahubKind.GLOBALPREFERENCE)
        assert len(preferences) == 1
        assert preferences[0].date_format.value is None
        assert preferences[0].timezone.value is None

        # Re-running the migration must be idempotent
        async with db.start_session() as dbs:
            result = await Migration074().execute(migration_input=MigrationInput(db=dbs))
            assert not result.errors, result.errors

        assert await _count_permission_nodes(db=db) == 1
        assert await _count_global_preference_nodes(db=db) == 1
