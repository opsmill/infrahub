from __future__ import annotations

import pytest

from infrahub.git.divergence.models import RefClassification, RefDivergence

IMPORTED = "a" * 40
REMOTE = "b" * 40


def build(
    classification: RefClassification, imported: str | None = IMPORTED, remote: str | None = REMOTE
) -> RefDivergence:
    return RefDivergence(
        branch_name="main",
        infrahub_branch_name="main",
        imported_commit=imported,
        remote_head=remote,
        classification=classification,
    )


@pytest.mark.parametrize(
    "classification",
    [RefClassification.REWRITE, RefClassification.RETARGET],
)
def test_a_lineage_decision_needs_the_commit_it_compared(classification: RefClassification) -> None:
    with pytest.raises(ValueError, match=rf"^{classification} requires both an imported commit and a remote head"):
        build(classification, imported=None)


@pytest.mark.parametrize(
    "classification",
    [RefClassification.REWRITE, RefClassification.RETARGET],
)
def test_a_lineage_decision_needs_the_remote_head_it_compared(classification: RefClassification) -> None:
    with pytest.raises(ValueError, match=rf"^{classification} requires both an imported commit and a remote head"):
        build(classification, remote=None)


def test_a_never_imported_branch_cannot_be_remote_absent() -> None:
    with pytest.raises(ValueError, match=r"^A branch with no imported commit cannot be remote-absent$"):
        build(RefClassification.REMOTE_ABSENT, imported=None, remote=None)


def test_a_missing_remote_head_cannot_be_a_fast_forward() -> None:
    with pytest.raises(ValueError, match=r"^A branch with no remote head cannot be fast-forward$"):
        build(RefClassification.FAST_FORWARD, remote=None)


def test_an_imported_branch_whose_remote_ref_is_gone_is_not_unchanged() -> None:
    with pytest.raises(
        ValueError, match=r"^An imported branch whose remote head is gone is REMOTE_ABSENT, not UNCHANGED$"
    ):
        build(RefClassification.UNCHANGED, remote=None)


def test_a_branch_absent_from_both_sides_is_unchanged() -> None:
    result = build(RefClassification.UNCHANGED, imported=None, remote=None)

    assert result.classification is RefClassification.UNCHANGED


def test_a_never_imported_branch_can_fast_forward() -> None:
    result = build(RefClassification.FAST_FORWARD, imported=None)

    assert result.imported_commit is None


def test_an_imported_branch_can_lose_its_remote_ref() -> None:
    result = build(RefClassification.REMOTE_ABSENT, remote=None)

    assert result.classification is RefClassification.REMOTE_ABSENT
