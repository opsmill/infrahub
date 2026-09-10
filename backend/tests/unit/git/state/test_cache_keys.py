from __future__ import annotations

from infrahub.git.state.cache_keys import (
    refs_check_due_key,
    refs_check_last_key,
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
