from __future__ import annotations

import re
from dataclasses import dataclass

import pytest

from infrahub.git.divergence.models import RefClassification, RefDivergence
from tests.unit.git.divergence.conftest import IMPORTED, REMOTE


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


@dataclass
class CombinationTestCase:
    name: str
    classification: RefClassification
    imported: str | None
    remote: str | None
    message: str | None = None
    """The whole expected message, or None when the combination is accepted."""


COMBINATION_TEST_CASES: list[CombinationTestCase] = [
    CombinationTestCase(
        name="rewrite_without_an_imported_commit",
        classification=RefClassification.REWRITE,
        imported=None,
        remote=REMOTE,
        message="A branch with no imported commit cannot be rewrite",
    ),
    CombinationTestCase(
        name="retarget_without_an_imported_commit",
        classification=RefClassification.RETARGET,
        imported=None,
        remote=REMOTE,
        message="A branch with no imported commit cannot be retarget",
    ),
    CombinationTestCase(
        name="remote_absent_without_an_imported_commit",
        classification=RefClassification.REMOTE_ABSENT,
        imported=None,
        remote=None,
        message="A branch with no imported commit cannot be remote-absent",
    ),
    CombinationTestCase(
        name="rewrite_without_a_remote_head",
        classification=RefClassification.REWRITE,
        imported=IMPORTED,
        remote=None,
        message="A branch with no remote head cannot be rewrite",
    ),
    CombinationTestCase(
        name="retarget_without_a_remote_head",
        classification=RefClassification.RETARGET,
        imported=IMPORTED,
        remote=None,
        message="A branch with no remote head cannot be retarget",
    ),
    CombinationTestCase(
        name="fast_forward_without_a_remote_head",
        classification=RefClassification.FAST_FORWARD,
        imported=IMPORTED,
        remote=None,
        message="A branch with no remote head cannot be fast-forward",
    ),
    CombinationTestCase(
        name="rewrite_whose_commits_match",
        classification=RefClassification.REWRITE,
        imported=IMPORTED,
        remote=IMPORTED,
        message=f"A branch whose commits both read {IMPORTED} is unchanged, not rewrite",
    ),
    CombinationTestCase(
        name="retarget_whose_commits_match",
        classification=RefClassification.RETARGET,
        imported=IMPORTED,
        remote=IMPORTED,
        message=f"A branch whose commits both read {IMPORTED} is unchanged, not retarget",
    ),
    CombinationTestCase(
        name="fast_forward_whose_commits_match",
        classification=RefClassification.FAST_FORWARD,
        imported=IMPORTED,
        remote=IMPORTED,
        message=f"A branch whose commits both read {IMPORTED} is unchanged, not fast-forward",
    ),
    CombinationTestCase(
        name="unchanged_whose_commits_differ",
        classification=RefClassification.UNCHANGED,
        imported=IMPORTED,
        remote=REMOTE,
        message=f"A branch is not unchanged when {IMPORTED} was imported and the remote reads {REMOTE}",
    ),
    CombinationTestCase(
        name="unchanged_that_was_never_imported",
        classification=RefClassification.UNCHANGED,
        imported=None,
        remote=REMOTE,
        message=f"A branch is not unchanged when None was imported and the remote reads {REMOTE}",
    ),
    CombinationTestCase(
        name="unchanged_whose_remote_head_is_gone",
        classification=RefClassification.UNCHANGED,
        imported=IMPORTED,
        remote=None,
        message=f"A branch is not unchanged when {IMPORTED} was imported and the remote reads None",
    ),
    CombinationTestCase(
        name="unchanged_absent_from_both_sides",
        classification=RefClassification.UNCHANGED,
        imported=None,
        remote=None,
    ),
    CombinationTestCase(
        name="fast_forward_of_a_branch_never_imported",
        classification=RefClassification.FAST_FORWARD,
        imported=None,
        remote=REMOTE,
    ),
    CombinationTestCase(
        name="remote_absent_after_the_ref_was_dropped",
        classification=RefClassification.REMOTE_ABSENT,
        imported=IMPORTED,
        remote=None,
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in COMBINATION_TEST_CASES],
)
def test_only_a_coherent_combination_is_accepted(test_case: CombinationTestCase) -> None:
    if test_case.message is None:
        build(test_case.classification, imported=test_case.imported, remote=test_case.remote)
        return

    with pytest.raises(ValueError, match=rf"^{re.escape(test_case.message)}$"):
        build(test_case.classification, imported=test_case.imported, remote=test_case.remote)
