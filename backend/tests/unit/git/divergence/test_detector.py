from __future__ import annotations

import pytest

from infrahub.exceptions import RepositoryError
from infrahub.git.divergence.detector import RemoteDivergenceDetector
from infrahub.git.divergence.models import RefClassification, RefDivergence

IMPORTED = "a" * 40
REMOTE = "b" * 40


class FakeAncestryGateway:
    """An object database whose contents and ancestry edges the test states up front."""

    def __init__(
        self,
        present: set[str] | None = None,
        ancestors: set[tuple[str, str]] | None = None,
        fail_with: RepositoryError | None = None,
    ) -> None:
        self.present = present if present is not None else {IMPORTED, REMOTE}
        self.ancestors = ancestors or set()
        self.fail_with = fail_with
        self.is_ancestor_calls: list[tuple[str, str]] = []

    def has_commit(self, commit: str) -> bool:
        return commit in self.present

    def is_ancestor(self, ancestor_commit: str, descendant_commit: str) -> bool:
        self.is_ancestor_calls.append((ancestor_commit, descendant_commit))
        if self.fail_with:
            raise self.fail_with
        return (ancestor_commit, descendant_commit) in self.ancestors


def classify(
    gateway: FakeAncestryGateway, imported: str | None, remote: str | None, target_changed: bool = False
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


def test_branch_ahead_of_its_remote_is_not_a_rewrite() -> None:
    """The reset discards an unpushed commit if this comes out REWRITE."""
    gateway = FakeAncestryGateway(ancestors={(REMOTE, IMPORTED)})

    result = classify(gateway, imported=IMPORTED, remote=REMOTE)

    assert result.classification is RefClassification.LOCAL_AHEAD


def test_unrelated_histories_are_a_rewrite() -> None:
    result = classify(FakeAncestryGateway(), imported=IMPORTED, remote=REMOTE)

    assert result.classification is RefClassification.REWRITE


def test_unrelated_histories_after_a_retarget_are_not_a_rewrite() -> None:
    result = classify(FakeAncestryGateway(), imported=IMPORTED, remote=REMOTE, target_changed=True)

    assert result.classification is RefClassification.RETARGET


def test_garbage_collected_imported_commit_is_a_rewrite() -> None:
    gateway = FakeAncestryGateway(present={REMOTE})

    result = classify(gateway, imported=IMPORTED, remote=REMOTE)

    assert result.classification is RefClassification.REWRITE


def test_garbage_collected_imported_commit_after_a_retarget_is_not_a_rewrite() -> None:
    gateway = FakeAncestryGateway(present={REMOTE})

    result = classify(gateway, imported=IMPORTED, remote=REMOTE, target_changed=True)

    assert result.classification is RefClassification.RETARGET


def test_absent_object_is_decided_without_asking_about_ancestry() -> None:
    """The ancestry call raises rather than answering once the object is gone."""
    gateway = FakeAncestryGateway(present={REMOTE}, fail_with=RepositoryError(identifier="repo"))

    result = classify(gateway, imported=IMPORTED, remote=REMOTE)

    assert result.classification is RefClassification.REWRITE
    assert gateway.is_ancestor_calls == []


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
