import os
import shutil
from typing import Dict

import pytest
from git.repo import Repo

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

    name = "infrahub-demo-edge"
    fixtures_dir = helper.get_fixtures_dir()

    test_base = os.path.join(fixtures_dir, f"repos/{name}")
    shutil.copytree(test_base, f"{git_sources_dir}/{name}")
    origin = Repo.init(f"{git_sources_dir}/{name}", initial_branch="main")
    for untracked in origin.untracked_files:
        origin.index.add(untracked)
    origin.index.commit("First commit")

    return dict(name=name, path=str(os.path.join(git_sources_dir, name)))
