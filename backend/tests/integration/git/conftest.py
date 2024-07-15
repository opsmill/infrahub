from pathlib import Path

import pytest

from infrahub import config
from tests.helpers.file_repo import FileRepo


@pytest.fixture
def git_sources_dir(tmp_path: Path) -> Path:
    source_dir = tmp_path / "sources"
    source_dir.mkdir()

    return source_dir


@pytest.fixture
def git_repos_dir(tmp_path: Path) -> Path:
    repos_dir = tmp_path / "repositories"
    repos_dir.mkdir()

    config.SETTINGS.git.repositories_directory = str(repos_dir)

    return repos_dir


@pytest.fixture
def git_repo_infrahub_demo_edge(git_sources_dir: Path) -> FileRepo:
    """Git Repository used as part of the  demo-edge tutorial."""

    return FileRepo(name="infrahub-demo-edge", sources_directory=git_sources_dir)
