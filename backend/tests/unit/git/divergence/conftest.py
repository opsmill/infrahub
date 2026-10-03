from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from git import Repo

from infrahub.git.divergence.gateway import GitPythonAncestryGateway

IMPORTED = "a" * 40
REMOTE = "b" * 40
ABSENT = "0" * 40


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo.init(tmp_path / "repository")


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
