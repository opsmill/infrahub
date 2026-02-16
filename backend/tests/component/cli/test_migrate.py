from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest

from infrahub.cli.db import do_migrate
from infrahub.core.branch import Branch
from infrahub.core.initialization import get_root_node
from infrahub.core.migrations.shared import GraphMigration, MigrationResult
from infrahub.database import InfrahubDatabase


@dataclass
class DoMigrateTestCase:
    """Test case parameters for do_migrate tests."""

    check: bool
    migration_number: int | None
    expected_version_number: int
    description: str


class Migration001(GraphMigration):
    """Dummy migration for testing purposes with name matching migration number 1."""

    name: str = "001_dummy_migration"
    minimum_version: int = 0
    queries: list = []

    async def validate_migration(self, db: InfrahubDatabase):
        return MigrationResult()


class Migration042(GraphMigration):
    """Dummy migration for testing purposes with name matching migration number 42."""

    name: str = "042_dummy_migration"
    minimum_version: int = 41
    queries: list = []

    async def validate_migration(self, db: InfrahubDatabase):
        return MigrationResult()


class TestDoMigrate:
    @pytest.mark.parametrize(
        "test_case",
        [
            DoMigrateTestCase(
                check=False,
                migration_number=None,
                expected_version_number=1,
                description="Normal run: should update graph version",
            ),
            DoMigrateTestCase(
                check=True,
                migration_number=None,
                expected_version_number=0,
                description="Check only: should not update graph version",
            ),
            DoMigrateTestCase(
                check=False,
                migration_number=1,
                expected_version_number=0,
                description="Specific migration: should not update graph version",
            ),
            DoMigrateTestCase(
                check=True,
                migration_number=1,
                expected_version_number=0,
                description="Check with specific migration: should not update graph version",
            ),
        ],
        ids=lambda tc: tc.description,
    )
    async def test_do_migrate_check_flag(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        test_case: DoMigrateTestCase,
    ):
        """Test that check=True prevents migrations from running."""
        root_node = await get_root_node(db=db)
        initial_version = root_node.graph_version

        # Set graph version to 0 so Migration001 is applicable
        root_node.graph_version = 0
        await root_node.save(db=db)

        with patch("infrahub.core.migrations.graph.MIGRATIONS", [Migration001]):
            await do_migrate(
                db=db,
                root_node=root_node,
                check=test_case.check,
                migration_number=test_case.migration_number,
            )

        # Reload root node to check if version changed
        root_node = await get_root_node(db=db)

        assert root_node.graph_version == test_case.expected_version_number

        # Restore original version for other tests
        root_node.graph_version = initial_version
        await root_node.save(db=db)

    async def test_do_migrate_no_migrations_to_run(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
    ):
        """Test that no changes occur when no migrations are applicable."""
        root_node = await get_root_node(db=db)
        initial_version = root_node.graph_version

        # Set graph version higher than Migration001's minimum_version
        root_node.graph_version = 100
        await root_node.save(db=db)

        with patch("infrahub.core.migrations.graph.MIGRATIONS", [Migration001]):
            await do_migrate(
                db=db,
                root_node=root_node,
                check=False,
                migration_number=None,
            )

        # Reload and verify no change
        root_node = await get_root_node(db=db)
        assert root_node.graph_version == 100

        # Restore original version
        root_node.graph_version = initial_version
        await root_node.save(db=db)

    async def test_do_migrate_update_graph_version_true_without_migration_number(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
    ):
        """Test that update_graph_version=True when no specific migration is requested."""
        root_node = await get_root_node(db=db)
        initial_version = root_node.graph_version

        # Set graph version to 0 so Migration001 is applicable
        root_node.graph_version = 0
        await root_node.save(db=db)

        with patch("infrahub.core.migrations.graph.MIGRATIONS", [Migration001]):
            await do_migrate(
                db=db,
                root_node=root_node,
                check=False,
                migration_number=None,
            )

        # Reload and verify version updated
        root_node = await get_root_node(db=db)
        assert root_node.graph_version == 1  # Migration001.minimum_version + 1

        # Restore original version
        root_node.graph_version = initial_version
        await root_node.save(db=db)

    async def test_do_migrate_update_graph_version_false_with_migration_number(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
    ):
        """Test that update_graph_version=False when a specific migration is requested."""
        root_node = await get_root_node(db=db)
        initial_version = root_node.graph_version

        # Set graph version to 0 so Migration001 is applicable
        root_node.graph_version = 0
        await root_node.save(db=db)

        mock_execute = AsyncMock(return_value=MigrationResult())

        with (
            patch("infrahub.core.migrations.graph.MIGRATIONS", [Migration001]),
            patch.object(Migration001, "execute", mock_execute),
        ):
            await do_migrate(
                db=db,
                root_node=root_node,
                check=False,
                migration_number=1,
            )

            # Verify migration was executed
            mock_execute.assert_awaited_once()

        # Reload and verify version NOT updated (because migration_number was specified)
        root_node = await get_root_node(db=db)
        assert root_node.graph_version == 0

        # Restore original version
        root_node.graph_version = initial_version
        await root_node.save(db=db)

    async def test_do_migrate_runs_specific_migration_by_number(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
    ):
        """Test that migration_number selects the correct migration."""
        root_node = await get_root_node(db=db)
        initial_version = root_node.graph_version

        # Set graph version high enough that Migration001 would be skipped in normal run
        # but Migration042 would be found by number
        root_node.graph_version = 50
        await root_node.save(db=db)

        with patch("infrahub.core.migrations.graph.MIGRATIONS", [Migration001, Migration042]):
            await do_migrate(
                db=db,
                root_node=root_node,
                check=False,
                migration_number=42,
            )

        # Migration ran but version not updated (because migration_number was specified)
        root_node = await get_root_node(db=db)
        assert root_node.graph_version == 50

        # Restore original version
        root_node.graph_version = initial_version
        await root_node.save(db=db)

    async def test_do_migrate_reruns_already_applied_migration(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
    ):
        """Test that a specific migration can be re-run even if already applied."""
        root_node = await get_root_node(db=db)
        initial_version = root_node.graph_version

        # Set graph version higher than Migration001's minimum_version (already applied)
        root_node.graph_version = 10
        await root_node.save(db=db)

        mock_execute = AsyncMock(return_value=MigrationResult())

        with (
            patch("infrahub.core.migrations.graph.MIGRATIONS", [Migration001]),
            patch.object(Migration001, "execute", mock_execute),
        ):
            # This should still run Migration001 because migration_number is specified
            await do_migrate(
                db=db,
                root_node=root_node,
                check=False,
                migration_number=1,
            )

            # Verify migration was executed even though it was already applied
            mock_execute.assert_awaited_once()

        # Version should not change (migration_number specified)
        root_node = await get_root_node(db=db)
        assert root_node.graph_version == 10

        # Restore original version
        root_node.graph_version = initial_version
        await root_node.save(db=db)
