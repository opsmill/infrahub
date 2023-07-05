import os
import tarfile
from typing import Dict

import pytest

import infrahub.config as config


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
def git_upstream_repo_10(helper, git_sources_dir) -> Dict[str, str]:
    """Git Repository used as part of the  demo-edge tutorial."""

    name = "infrahub-demo-edge-develop"
    fixtures_dir = helper.get_fixtures_dir()
    fixture_repo = os.path.join(fixtures_dir, "infrahub-demo-edge-develop-8d18455.tar.gz")

    # Extract the fixture package in the source directory
    file = tarfile.open(fixture_repo)
    file.extractall(git_sources_dir)
    file.close()

    return dict(name=name, path=str(os.path.join(git_sources_dir, name)))
