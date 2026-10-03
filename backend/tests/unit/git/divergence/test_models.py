from __future__ import annotations

import re

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


@pytest.mark.parametrize(
    ("classification", "imported", "remote", "message"),
    [
        (RefClassification.REWRITE, None, REMOTE, "A branch with no imported commit cannot be rewrite"),
        (RefClassification.RETARGET, None, REMOTE, "A branch with no imported commit cannot be retarget"),
        (
            RefClassification.REMOTE_ABSENT,
            None,
            None,
            "A branch with no imported commit cannot be remote-absent",
        ),
        (RefClassification.REWRITE, IMPORTED, None, "A branch with no remote head cannot be rewrite"),
        (RefClassification.RETARGET, IMPORTED, None, "A branch with no remote head cannot be retarget"),
        (RefClassification.FAST_FORWARD, IMPORTED, None, "A branch with no remote head cannot be fast-forward"),
        (
            RefClassification.UNCHANGED,
            IMPORTED,
            None,
            "An imported branch whose remote head is gone is REMOTE_ABSENT, not UNCHANGED",
        ),
    ],
)
def test_a_rejected_combination_raises(
    classification: RefClassification, imported: str | None, remote: str | None, message: str
) -> None:
    with pytest.raises(ValueError, match=rf"^{re.escape(message)}$"):
        build(classification, imported=imported, remote=remote)


@pytest.mark.parametrize(
    ("classification", "imported", "remote"),
    [
        pytest.param(RefClassification.UNCHANGED, None, None, id="absent-from-both-sides"),
        pytest.param(RefClassification.FAST_FORWARD, None, REMOTE, id="never-imported-branch"),
        pytest.param(RefClassification.REMOTE_ABSENT, IMPORTED, None, id="remote-ref-is-gone"),
    ],
)
def test_an_accepted_combination_builds(
    classification: RefClassification, imported: str | None, remote: str | None
) -> None:
    build(classification, imported=imported, remote=remote)
