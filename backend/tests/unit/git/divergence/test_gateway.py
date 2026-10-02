from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo

from infrahub.exceptions import RepositoryError
from infrahub.git.divergence.gateway import GitPythonAncestryGateway


def commit_file(repo: Repo, content: str) -> str:
    working_tree = repo.working_tree_dir
    assert working_tree is not None
    Path(working_tree, "file.txt").write_text(content, encoding="utf-8")
    repo.index.add(["file.txt"])
    return str(repo.index.commit(f"commit {content}").hexsha)


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


def test_an_earlier_commit_is_an_ancestor_of_a_later_one(repo: Repo, gateway: GitPythonAncestryGateway) -> None:
    first = commit_file(repo=repo, content="one")
    second = commit_file(repo=repo, content="two")

    assert gateway.is_ancestor(ancestor_commit=first, descendant_commit=second) is True
    assert gateway.is_ancestor(ancestor_commit=second, descendant_commit=first) is False


def test_an_unreachable_commit_leaves_as_a_repository_error(repo: Repo, gateway: GitPythonAncestryGateway) -> None:
    present = commit_file(repo=repo, content="one")
    absent = "0" * 40

    with pytest.raises(RepositoryError, match=r"Unable to compare"):
        gateway.is_ancestor(ancestor_commit=absent, descendant_commit=present)


def test_a_commit_in_the_object_database_is_present(repo: Repo, gateway: GitPythonAncestryGateway) -> None:
    assert gateway.has_commit(commit=commit_file(repo=repo, content="one")) is True


def test_a_packed_commit_is_still_present(repo: Repo, gateway: GitPythonAncestryGateway) -> None:
    """Packing moves the object out of its loose file, and it must still read as present."""
    commit = commit_file(repo=repo, content="one")
    commit_file(repo=repo, content="two")
    repo.git.gc("--prune=now")

    assert gateway.has_commit(commit=commit) is True


def test_a_pruned_commit_reads_as_absent_rather_than_raising(repo: Repo, gateway: GitPythonAncestryGateway) -> None:
    """Without this the branch raises every cycle and never classifies at all."""
    keep = commit_file(repo=repo, content="one")
    pruned = commit_file(repo=repo, content="two")
    repo.git.reset("--hard", keep)
    repo.git.reflog("expire", "--expire=now", "--all")
    repo.git.prune()

    assert gateway.has_commit(commit=pruned) is False


def test_a_malformed_commit_identifier_is_an_error_not_an_absence(gateway: GitPythonAncestryGateway) -> None:
    with pytest.raises(RepositoryError, match=r"is not a valid commit identifier"):
        gateway.has_commit(commit="not-a-sha")
