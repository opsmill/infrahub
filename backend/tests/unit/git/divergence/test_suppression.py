from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.git.divergence.suppression import RetargetMarkers
from tests.adapters.cache import MemoryCache

REPOSITORY_ID = "repository-id"
OTHER_REPOSITORY_ID = "other-repository-id"
NEW_TARGET = "release"
OLD_TARGET = "main"


async def marked_markers() -> RetargetMarkers:
    markers = RetargetMarkers(cache=MemoryCache())
    await markers.mark(repository_id=REPOSITORY_ID, infrahub_branch_name="main", target=NEW_TARGET)
    return markers


@dataclass
class ReadTestCase:
    name: str
    repository_id: str
    infrahub_branch_name: str
    target: str
    expected: bool


READ_TEST_CASES: list[ReadTestCase] = [
    ReadTestCase(
        name="marker_that_names_the_target",
        repository_id=REPOSITORY_ID,
        infrahub_branch_name="main",
        target=NEW_TARGET,
        expected=True,
    ),
    ReadTestCase(
        name="marker_that_names_another_target",
        repository_id=REPOSITORY_ID,
        infrahub_branch_name="main",
        target=OLD_TARGET,
        expected=False,
    ),
    ReadTestCase(
        name="no_marker_on_another_branch",
        repository_id=REPOSITORY_ID,
        infrahub_branch_name="feature",
        target=NEW_TARGET,
        expected=False,
    ),
    ReadTestCase(
        name="no_marker_on_another_repository",
        repository_id=OTHER_REPOSITORY_ID,
        infrahub_branch_name="main",
        target=NEW_TARGET,
        expected=False,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in READ_TEST_CASES])
async def test_a_branch_reads_as_re_pointed_only_at_the_target_its_marker_names(test_case: ReadTestCase) -> None:
    markers = await marked_markers()

    assert (
        await markers.is_retargeted(
            repository_id=test_case.repository_id,
            infrahub_branch_name=test_case.infrahub_branch_name,
            target=test_case.target,
        )
        is test_case.expected
    )


async def test_reading_a_marker_leaves_it_in_place() -> None:
    markers = await marked_markers()

    await markers.is_retargeted(repository_id=REPOSITORY_ID, infrahub_branch_name="main", target=NEW_TARGET)

    assert await markers.is_retargeted(repository_id=REPOSITORY_ID, infrahub_branch_name="main", target=NEW_TARGET)


async def test_a_cleared_marker_no_longer_applies() -> None:
    markers = await marked_markers()

    await markers.clear(repository_id=REPOSITORY_ID, infrahub_branch_name="main", target=NEW_TARGET)

    assert not await markers.is_retargeted(repository_id=REPOSITORY_ID, infrahub_branch_name="main", target=NEW_TARGET)


async def test_clearing_for_another_target_keeps_the_marker() -> None:
    markers = await marked_markers()

    await markers.clear(repository_id=REPOSITORY_ID, infrahub_branch_name="main", target=OLD_TARGET)

    assert await markers.is_retargeted(repository_id=REPOSITORY_ID, infrahub_branch_name="main", target=NEW_TARGET)


async def test_a_marker_expires_after_seven_days() -> None:
    cache = MemoryCache()

    await RetargetMarkers(cache=cache).mark(repository_id=REPOSITORY_ID, infrahub_branch_name="main", target=NEW_TARGET)

    assert list(cache.expiries.values()) == [604800]
