from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.git.divergence.suppression import RetargetMarkers
from tests.adapters.cache import MemoryCache

REPOSITORY_ID = "repository-id"
OTHER_REPOSITORY_ID = "other-repository-id"
NEW_TARGET = "release"
OLD_TARGET = "main"
LATER_TARGET = "hotfix"


async def marked_markers() -> RetargetMarkers:
    markers = RetargetMarkers(cache=MemoryCache())
    await markers.mark(repository_id=REPOSITORY_ID, target=NEW_TARGET)
    return markers


class CacheWrittenDuringTheClear(MemoryCache):
    """Applies a pending write right after the first call it receives, as an edit that lands during a clear does."""

    def __init__(self, pending: dict[str, str]) -> None:
        super().__init__()
        self.pending = pending

    def _land_pending_write(self) -> None:
        self.storage.update(self.pending)
        self.pending = {}

    async def get(self, key: str) -> str | None:
        value = await super().get(key)
        self._land_pending_write()
        return value

    async def delete(self, key: str) -> None:
        await super().delete(key)
        self._land_pending_write()


@dataclass
class ReadTestCase:
    name: str
    repository_id: str
    target: str
    expected: bool


READ_TEST_CASES: list[ReadTestCase] = [
    ReadTestCase(name="marker_for_the_target", repository_id=REPOSITORY_ID, target=NEW_TARGET, expected=True),
    ReadTestCase(name="marker_for_another_target", repository_id=REPOSITORY_ID, target=OLD_TARGET, expected=False),
    ReadTestCase(
        name="no_marker_on_another_repository", repository_id=OTHER_REPOSITORY_ID, target=NEW_TARGET, expected=False
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in READ_TEST_CASES])
async def test_a_repository_reads_as_re_pointed_only_at_a_target_it_was_marked_for(test_case: ReadTestCase) -> None:
    markers = await marked_markers()

    assert (
        await markers.is_retargeted(repository_id=test_case.repository_id, target=test_case.target)
        is test_case.expected
    )


async def test_reading_a_marker_leaves_it_in_place() -> None:
    markers = await marked_markers()

    await markers.is_retargeted(repository_id=REPOSITORY_ID, target=NEW_TARGET)

    assert await markers.is_retargeted(repository_id=REPOSITORY_ID, target=NEW_TARGET)


async def test_a_cleared_marker_no_longer_applies() -> None:
    markers = await marked_markers()

    await markers.clear(repository_id=REPOSITORY_ID, target=NEW_TARGET)

    assert not await markers.is_retargeted(repository_id=REPOSITORY_ID, target=NEW_TARGET)


async def test_clearing_another_target_keeps_the_marker() -> None:
    markers = await marked_markers()

    await markers.clear(repository_id=REPOSITORY_ID, target=OLD_TARGET)

    assert await markers.is_retargeted(repository_id=REPOSITORY_ID, target=NEW_TARGET)


async def test_a_marker_for_another_target_keeps_the_marker_the_sync_needs() -> None:
    """An update to another target can roll back after its marker is written, and the earlier change still stands."""
    markers = await marked_markers()

    await markers.mark(repository_id=REPOSITORY_ID, target=LATER_TARGET)

    assert await markers.is_retargeted(repository_id=REPOSITORY_ID, target=NEW_TARGET)


async def test_a_marker_for_another_target_written_during_a_clear_survives_it() -> None:
    edit = MemoryCache()
    await RetargetMarkers(cache=edit).mark(repository_id=REPOSITORY_ID, target=LATER_TARGET)
    markers = RetargetMarkers(cache=CacheWrittenDuringTheClear(pending=edit.storage))
    await markers.mark(repository_id=REPOSITORY_ID, target=NEW_TARGET)

    await markers.clear(repository_id=REPOSITORY_ID, target=NEW_TARGET)

    assert await markers.is_retargeted(repository_id=REPOSITORY_ID, target=LATER_TARGET)


async def test_a_marker_expires_after_seven_days() -> None:
    cache = MemoryCache()

    await RetargetMarkers(cache=cache).mark(repository_id=REPOSITORY_ID, target=NEW_TARGET)

    assert list(cache.expiries.values()) == [604800]
