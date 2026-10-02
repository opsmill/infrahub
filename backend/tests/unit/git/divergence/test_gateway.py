from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.exceptions import RepositoryError
from tests.unit.git.divergence.conftest import break_object_database, commit_file

if TYPE_CHECKING:
    from git import Repo

    from infrahub.git.divergence.gateway import GitPythonAncestryGateway


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


@pytest.mark.parametrize("identifier", ["not-a-sha", "abcd", "0" * 39, "0" * 41])
def test_a_malformed_commit_identifier_is_an_error_not_an_absence(
    gateway: GitPythonAncestryGateway, identifier: str
) -> None:
    """An identifier that is not a full sha must not be reported as a pruned commit."""
    with pytest.raises(RepositoryError, match=r"is not a valid commit identifier"):
        gateway.has_commit(commit=identifier)


def test_a_broken_object_database_is_an_error_not_an_absence(repo: Repo, gateway: GitPythonAncestryGateway) -> None:
    """A reader that cannot answer must not be read as a pruned commit."""
    commit = commit_file(repo=repo, content="one")
    break_object_database(repo=repo)

    with pytest.raises(RepositoryError, match=r"Unable to read"):
        gateway.has_commit(commit=commit)
