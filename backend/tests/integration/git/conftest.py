import os

import pytest

from infrahub import config
from tests.helpers.file_repo import FileRepo


@pytest.fixture
def git_sources_dir(tmp_path) -> str:
    source_dir = os.path.join(str(tmp_path), "sources")

    os.mkdir(source_dir)

    return source_dir


@pytest.fixture
def git_repos_dir(tmp_path) -> str:
    repos_dir = os.path.join(str(tmp_path), "repositories")

    os.mkdir(repos_dir)

    config.SETTINGS.git.repositories_directory = repos_dir

    return repos_dir


@pytest.fixture
def git_repo_infrahub_demo_edge(git_sources_dir) -> FileRepo:
    """Git Repository used as part of the  demo-edge tutorial."""

    return FileRepo(name="infrahub-demo-edge", sources_directory=git_sources_dir)
