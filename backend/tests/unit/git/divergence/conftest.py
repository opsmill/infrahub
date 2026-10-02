from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from git import Repo

from infrahub.git.divergence.gateway import GitPythonAncestryGateway


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    created = Repo.init(tmp_path / "repository")
    with created.config_writer() as config:
        config.set_value("user", "email", "test@example.com")
        config.set_value("user", "name", "Test")
    return created


@pytest.fixture
def gateway(repo: Repo) -> GitPythonAncestryGateway:
    return GitPythonAncestryGateway(repository_name="test-repository", repo=repo)


def commit_file(repo: Repo, content: str) -> str:
    working_tree = repo.working_tree_dir
    assert working_tree is not None
    Path(working_tree, "file.txt").write_text(content, encoding="utf-8")
    repo.index.add(["file.txt"])
    return str(repo.index.commit(f"commit {content}").hexsha)


def break_object_database(repo: Repo) -> None:
    """Leave git unable to answer anything about this repository."""
    shutil.rmtree(Path(str(repo.git_dir), "objects"))
