from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.exceptions import RepositoryError
from infrahub.git.divergence.detector import RemoteDivergenceDetector
from infrahub.git.divergence.models import RefClassification, RefDivergence
from tests.unit.git.divergence.conftest import ABSENT, IMPORTED, REMOTE, break_object_database, commit_file

if TYPE_CHECKING:
    from git import Repo

    from infrahub.git.divergence.gateway import GitAncestryGateway
    from infrahub.git.divergence.protocols import AncestryGateway


class FakeAncestryGateway:
    """An object database whose contents and ancestry edges the test states up front."""

    def __init__(
        self,
        present: set[str] | None = None,
        ancestors: set[tuple[str, str]] | None = None,
        fail_with: RepositoryError | None = None,
        well_formed: set[str] | None = None,
    ) -> None:
        self.present = present if present is not None else {IMPORTED, REMOTE}
        self.well_formed = well_formed if well_formed is not None else {IMPORTED, REMOTE}
        self.ancestors = ancestors or set()
        self.fail_with = fail_with
        self.is_ancestor_calls: list[tuple[str, str]] = []

    def require_commit(self, commit: str) -> None:
        if commit not in self.well_formed:
            raise RepositoryError(identifier="repo", message=f"{commit!r} is not a valid commit identifier")

    def has_commit(self, commit: str) -> bool:
        return commit in self.present

    def is_ancestor(self, ancestor_commit: str, descendant_commit: str) -> bool:
        self.is_ancestor_calls.append((ancestor_commit, descendant_commit))
        if self.fail_with:
            raise self.fail_with
        return (ancestor_commit, descendant_commit) in self.ancestors


def classify(
    gateway: AncestryGateway, imported: str | None, remote: str | None, target_changed: bool = False
) -> RefDivergence:
    return RemoteDivergenceDetector(gateway=gateway).classify(
        branch_name="main",
        infrahub_branch_name="main",
        imported_commit=imported,
        remote_head=remote,
        target_changed=target_changed,
    )


def test_remote_ref_gone_from_an_imported_branch_is_not_a_lineage_break() -> None:
    result = classify(FakeAncestryGateway(), imported=IMPORTED, remote=None)

    assert result.classification is RefClassification.REMOTE_ABSENT


def test_branch_absent_from_both_sides_is_unchanged() -> None:
    result = classify(FakeAncestryGateway(), imported=None, remote=None)

    assert result.classification is RefClassification.UNCHANGED


def test_never_imported_branch_takes_the_ordinary_import_path() -> None:
    result = classify(FakeAncestryGateway(), imported=None, remote=REMOTE)

    assert result.classification is RefClassification.FAST_FORWARD


def test_matching_commits_are_unchanged() -> None:
    result = classify(FakeAncestryGateway(), imported=IMPORTED, remote=IMPORTED)

    assert result.classification is RefClassification.UNCHANGED


def test_advanced_remote_is_a_fast_forward() -> None:
    gateway = FakeAncestryGateway(ancestors={(IMPORTED, REMOTE)})

    result = classify(gateway, imported=IMPORTED, remote=REMOTE)

    assert result.classification is RefClassification.FAST_FORWARD


@dataclass
class LostCommitTestCase:
    name: str
    present: set[str] | None
    """What the object database still holds, or None for everything the test declared."""

    target_changed: bool
    expected: RefClassification


LOST_COMMIT_TEST_CASES: list[LostCommitTestCase] = [
    LostCommitTestCase(
        name="unrelated_histories_are_a_rewrite",
        present=None,
        target_changed=False,
        expected=RefClassification.REWRITE,
    ),
    LostCommitTestCase(
        name="unrelated_histories_after_a_retarget",
        present=None,
        target_changed=True,
        expected=RefClassification.RETARGET,
    ),
    LostCommitTestCase(
        name="garbage_collected_commit_is_a_rewrite",
        present={REMOTE},
        target_changed=False,
        expected=RefClassification.REWRITE,
    ),
    LostCommitTestCase(
        name="garbage_collected_commit_after_a_retarget",
        present={REMOTE},
        target_changed=True,
        expected=RefClassification.RETARGET,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in LOST_COMMIT_TEST_CASES])
def test_a_lost_imported_commit_is_a_rewrite_unless_the_target_changed(test_case: LostCommitTestCase) -> None:
    """Whatever lost the commit, only a deliberate re-target suppresses the record."""
    gateway = FakeAncestryGateway(present=test_case.present, ancestors=set())

    result = classify(gateway, imported=IMPORTED, remote=REMOTE, target_changed=test_case.target_changed)

    assert result.classification is test_case.expected


def test_absent_object_is_decided_without_asking_about_ancestry() -> None:
    """The ancestry call raises rather than answering once the object is gone."""
    gateway = FakeAncestryGateway(present={REMOTE}, fail_with=RepositoryError(identifier="repo"))

    result = classify(gateway, imported=IMPORTED, remote=REMOTE)

    assert result.classification is RefClassification.REWRITE
    assert gateway.is_ancestor_calls == []


def test_a_malformed_remote_head_raises_even_when_the_imported_commit_is_gone() -> None:
    """The absent commit alone would answer, so nothing else checks the other identifier."""
    gateway = FakeAncestryGateway(present=set(), well_formed={IMPORTED})

    with pytest.raises(RepositoryError, match=r"is not a valid commit identifier"):
        classify(gateway, imported=IMPORTED, remote=REMOTE)


def test_an_unchanged_ref_is_not_validated() -> None:
    """It needs no comparison, so the contract promises it raises nothing."""
    gateway = FakeAncestryGateway(well_formed=set())

    result = classify(gateway, imported=IMPORTED, remote=IMPORTED)

    assert result.classification is RefClassification.UNCHANGED


def test_git_failure_reaches_the_caller() -> None:
    gateway = FakeAncestryGateway(fail_with=RepositoryError(identifier="repo", message="index.lock exists"))

    with pytest.raises(RepositoryError, match=r"^index\.lock exists$"):
        classify(gateway, imported=IMPORTED, remote=REMOTE)


def test_result_carries_the_branch_and_both_commits() -> None:
    result = classify(FakeAncestryGateway(), imported=IMPORTED, remote=REMOTE)

    assert result.branch_name == "main"
    assert result.infrahub_branch_name == "main"
    assert result.imported_commit == IMPORTED
    assert result.remote_head == REMOTE


def test_a_real_repository_whose_remote_advanced_fast_forwards(repo: Repo, gateway: GitAncestryGateway) -> None:
    imported = commit_file(repo=repo, content="one")
    remote = commit_file(repo=repo, content="two")

    assert classify(gateway, imported=imported, remote=remote).classification is RefClassification.FAST_FORWARD


def test_a_real_repository_rewound_onto_an_ancestor_is_a_rewrite(repo: Repo, gateway: GitAncestryGateway) -> None:
    remote = commit_file(repo=repo, content="one")
    imported = commit_file(repo=repo, content="two")

    assert classify(gateway, imported=imported, remote=remote).classification is RefClassification.REWRITE


def test_a_real_repository_rewound_after_a_retarget_is_not_a_rewrite(repo: Repo, gateway: GitAncestryGateway) -> None:
    remote = commit_file(repo=repo, content="one")
    imported = commit_file(repo=repo, content="two")

    result = classify(gateway, imported=imported, remote=remote, target_changed=True)

    assert result.classification is RefClassification.RETARGET


def test_a_remote_head_missing_from_the_object_database_reaches_the_caller(
    repo: Repo, gateway: GitAncestryGateway
) -> None:
    imported = commit_file(repo=repo, content="one")

    with pytest.raises(RepositoryError, match=r"^Unable to compare [0-9a-f]{40} against 0{40}: "):
        classify(gateway, imported=imported, remote=ABSENT)


def test_a_broken_object_database_reaches_the_caller(repo: Repo, gateway: GitAncestryGateway) -> None:
    imported = commit_file(repo=repo, content="one")
    remote = commit_file(repo=repo, content="two")
    break_object_database(repo=repo)

    with pytest.raises(RepositoryError, match=r"^Unable to read [0-9a-f]{40} from the object database: "):
        classify(gateway, imported=imported, remote=remote)
