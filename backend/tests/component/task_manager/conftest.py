from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from tests.helpers.task_manager_seed import copy_task_manager_database, migrate_task_manager_database

if TYPE_CHECKING:
    from pathlib import Path


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
