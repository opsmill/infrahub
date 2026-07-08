from __future__ import annotations

from infrahub_sdk.schema.repository import InfrahubWatchConfig

from infrahub.git.fingerprint.composer import fold_commit_id


def test_absent_watch_folds_commit_id() -> None:
    assert fold_commit_id(commit="commit-1", watch=None, closure_complete=True) == "commit-1"


def test_present_empty_watch_omits_commit_id() -> None:
    assert fold_commit_id(commit="commit-1", watch=InfrahubWatchConfig(files=[]), closure_complete=True) is None


def test_present_populated_watch_omits_commit_id() -> None:
    watch = InfrahubWatchConfig(files=["helpers/util.py"])
    assert fold_commit_id(commit="commit-1", watch=watch, closure_complete=True) is None


def test_absent_and_present_empty_are_distinct_states() -> None:
    absent = fold_commit_id(commit="commit-1", watch=None, closure_complete=True)
    present_empty = fold_commit_id(commit="commit-1", watch=InfrahubWatchConfig(files=[]), closure_complete=True)
    assert absent is not None
    assert present_empty is None


def test_incomplete_closure_folds_commit_id_even_with_present_watch() -> None:
    # An incomplete closure means an output-affecting dependency is unknown, so the commit
    # id is folded to avoid a stable fingerprint over an unknown input set.
    assert fold_commit_id(commit="commit-1", watch=InfrahubWatchConfig(files=[]), closure_complete=False) == "commit-1"
