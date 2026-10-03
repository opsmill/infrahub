from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from infrahub.exceptions import RepositoryError
from tests.unit.git.divergence.conftest import ABSENT, break_object_database, commit_file

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

    with pytest.raises(RepositoryError, match=r"^Unable to compare 0{40} against [0-9a-f]{40}: "):
        gateway.is_ancestor(ancestor_commit=ABSENT, descendant_commit=present)


def test_a_broken_repository_fails_the_comparison(repo: Repo, gateway: GitPythonAncestryGateway) -> None:
    commit = commit_file(repo=repo, content="one")
    break_object_database(repo=repo)

    with pytest.raises(RepositoryError, match=r"^Unable to compare [0-9a-f]{40} against [0-9a-f]{40}: "):
        gateway.is_ancestor(ancestor_commit=commit, descendant_commit=commit)


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


def test_a_name_that_is_not_a_commit_holds_no_commit(repo: Repo, gateway: GitPythonAncestryGateway) -> None:
    """An annotated tag carries a commit, and its own object must still not read as one."""
    commit_file(repo=repo, content="one")
    tree = str(repo.head.commit.tree.hexsha)
    blob = str(repo.head.commit.tree["file.txt"].hexsha)
    annotated = repo.create_tag("v1", message="annotated").tag
    assert annotated is not None

    assert gateway.has_commit(commit=tree) is False
    assert gateway.has_commit(commit=blob) is False
    assert gateway.has_commit(commit=str(annotated.hexsha)) is False


def test_a_broken_object_database_is_an_error_not_an_absence(repo: Repo, gateway: GitPythonAncestryGateway) -> None:
    """A reader that cannot answer must not be read as a pruned commit."""
    commit = commit_file(repo=repo, content="one")
    break_object_database(repo=repo)

    with pytest.raises(RepositoryError, match=r"^Unable to read [0-9a-f]{40} from the object database: "):
        gateway.has_commit(commit=commit)


@pytest.mark.parametrize("identifier", ["not-a-sha", "abcd", "0" * 39, "0" * 41, "A" * 40])
def test_a_malformed_commit_identifier_is_an_error_not_an_absence(
    gateway: GitPythonAncestryGateway, identifier: str
) -> None:
    expected = re.escape(f"{identifier!r} is not a valid commit identifier")

    with pytest.raises(RepositoryError, match=rf"^{expected}$"):
        gateway.has_commit(commit=identifier)


@pytest.mark.parametrize("identifier", ["not-a-sha", "A" * 40])
def test_the_comparison_rejects_a_malformed_identifier(gateway: GitPythonAncestryGateway, identifier: str) -> None:
    expected = re.escape(f"{identifier!r} is not a valid commit identifier")

    with pytest.raises(RepositoryError, match=rf"^{expected}$"):
        gateway.is_ancestor(ancestor_commit=identifier, descendant_commit=ABSENT)

    with pytest.raises(RepositoryError, match=rf"^{expected}$"):
        gateway.is_ancestor(ancestor_commit=ABSENT, descendant_commit=identifier)
