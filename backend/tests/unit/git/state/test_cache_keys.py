from __future__ import annotations

import re

from infrahub.git.state.cache_keys import (
    activity_last_run_key,
    activity_run_key,
    activity_run_pattern,
    refs_check_due_key,
    refs_check_last_key,
    refs_check_listed_key,
    refs_check_running_key,
    warm_up_key,
)

REPOSITORY_ID = "18d39e83-1ef7-d650-5424-0242ac120005"


def test_the_cache_key_formats_are_stable() -> None:
    """One process writes these keys and another reads them, so a changed format is a silent miss."""
    assert warm_up_key(repository_id=REPOSITORY_ID) == "git:warmup:18d39e83-1ef7-d650-5424-0242ac120005"
    assert refs_check_due_key(repository_id=REPOSITORY_ID) == "git:refs_check:due:18d39e83-1ef7-d650-5424-0242ac120005"
    assert (
        refs_check_running_key(repository_id=REPOSITORY_ID)
        == "git:refs_check:running:18d39e83-1ef7-d650-5424-0242ac120005"
    )
    assert (
        refs_check_last_key(repository_id=REPOSITORY_ID) == "git:refs_check:last:18d39e83-1ef7-d650-5424-0242ac120005"
    )
    assert (
        refs_check_listed_key(repository_id=REPOSITORY_ID, ref="main")
        == "git:refs_check:listed:18d39e83-1ef7-d650-5424-0242ac120005:main"
    )
    assert (
        activity_run_key(repository_id=REPOSITORY_ID, run_id="run-1")
        == "git:activity:run:18d39e83-1ef7-d650-5424-0242ac120005:run-1"
    )
    assert (
        activity_last_run_key(repository_id=REPOSITORY_ID, operation="sync")
        == "git:activity:last:18d39e83-1ef7-d650-5424-0242ac120005:sync"
    )


def test_the_run_pattern_matches_the_runs_of_one_repository_only() -> None:
    pattern = re.compile(activity_run_pattern(repository_id=REPOSITORY_ID).replace("*", ".*"))

    assert pattern.fullmatch("git:activity:run:18d39e83-1ef7-d650-5424-0242ac120005:run-1")
    assert not pattern.fullmatch("git:activity:run:other-repository:run-1")
    assert not pattern.fullmatch("git:activity:last:18d39e83-1ef7-d650-5424-0242ac120005:sync")
