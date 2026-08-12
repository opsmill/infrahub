from __future__ import annotations

from dataclasses import dataclass

import pytest
from infrahub_sdk.schema.repository import InfrahubWatchConfig

from infrahub.git.fingerprint.composer import fold_commit_id


@dataclass
class FoldCase:
    name: str
    watch: InfrahubWatchConfig | None
    closure_complete: bool
    watch_required: bool
    folds: bool


FOLD_CASES = [
    # watch_required=True is how Python transforms and generators behave: their dependency list
    # is only the files next to the source file, so it can be missing an import from elsewhere
    # and a hand-written watch is the only thing that makes the fingerprint stable.
    FoldCase(
        name="watch_required_absent_watch_folds",
        watch=None,
        closure_complete=True,
        watch_required=True,
        folds=True,
    ),
    FoldCase(
        name="watch_required_empty_watch_omits",
        watch=InfrahubWatchConfig(files=[]),
        closure_complete=True,
        watch_required=True,
        folds=False,
    ),
    FoldCase(
        name="watch_required_populated_watch_omits",
        watch=InfrahubWatchConfig(files=["helpers/util.py"]),
        closure_complete=True,
        watch_required=True,
        folds=False,
    ),
    FoldCase(
        name="watch_required_incomplete_closure_folds_despite_watch",
        watch=InfrahubWatchConfig(files=[]),
        closure_complete=False,
        watch_required=True,
        folds=True,
    ),
    # watch_required=False is how Jinja2 transforms behave: their dependency list is parsed out
    # of the template, so a complete one needs no watch to make the fingerprint stable. An
    # incomplete list means a reference could not be followed, which still folds the commit id.
    FoldCase(
        name="watch_optional_absent_watch_complete_closure_omits",
        watch=None,
        closure_complete=True,
        watch_required=False,
        folds=False,
    ),
    FoldCase(
        name="watch_optional_absent_watch_incomplete_closure_folds",
        watch=None,
        closure_complete=False,
        watch_required=False,
        folds=True,
    ),
]


@pytest.mark.parametrize("case", FOLD_CASES, ids=lambda case: case.name)
def test_fold_commit_id(case: FoldCase) -> None:
    result = fold_commit_id(
        commit="commit-1",
        watch=case.watch,
        closure_complete=case.closure_complete,
        watch_required=case.watch_required,
    )
    assert result == ("commit-1" if case.folds else None)


def test_absent_and_present_empty_are_distinct_states_when_watch_required() -> None:
    absent = fold_commit_id(commit="commit-1", watch=None, closure_complete=True, watch_required=True)
    present_empty = fold_commit_id(
        commit="commit-1", watch=InfrahubWatchConfig(files=[]), closure_complete=True, watch_required=True
    )
    assert absent == "commit-1"
    assert present_empty is None
