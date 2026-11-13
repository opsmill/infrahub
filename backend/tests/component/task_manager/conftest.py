from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from prefect.server.database import provide_database_interface
from prefect.server.database.dependencies import temporary_database_interface
from prefect.settings import temporary_settings
from tests.helpers.task_manager_seed import copy_task_manager_database, migrate_task_manager_database

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from prefect.server.database import PrefectDBInterface


@pytest.fixture(scope="session")
def task_manager_database_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("task-manager-template") / "prefect.db"
    migrate_task_manager_database(path)
    return path


@pytest.fixture
def task_manager_database_path(task_manager_database_template: Path, tmp_path: Path) -> Path:
    """An empty, migrated task manager database of the test's own, apart from the one the test Prefect server uses."""
    path = tmp_path / "prefect.db"
    copy_task_manager_database(source=task_manager_database_template, target=path)
    return path


@pytest.fixture
def database(task_manager_database_path: Path) -> Generator[PrefectDBInterface, None, None]:
    """The test's own task manager database, set as the database Prefect reads and writes while the test runs."""
    # Prefect keeps the first database configuration it builds, so a new connection URL alone is not enough.
    with (
        temporary_database_interface(),
        temporary_settings(
            updates={"server.database.connection_url": f"sqlite+aiosqlite:///{task_manager_database_path}"}
        ),
    ):
        yield provide_database_interface()
