from dataclasses import dataclass

import pytest

from infrahub.core.merge.write_blocker import (
    MERGE_PROTECTED_CACHE_KEY,
    MergeProtection,
    MergeProtectionState,
    MergeWriteBlocker,
)
from tests.adapters.cache import MemoryCache


@dataclass
class ParseCase:
    name: str
    value: str | None
    expected: MergeProtection | None


PARSE_CASES = [
    ParseCase(
        name="merging",
        value="feature-branch::MERGING",
        expected=MergeProtection(branch="feature-branch", state=MergeProtectionState.MERGING),
    ),
    ParseCase(
        name="merge_failed",
        value="feature-branch::MERGE_FAILED",
        expected=MergeProtection(branch="feature-branch", state=MergeProtectionState.MERGE_FAILED),
    ),
    ParseCase(name="none", value=None, expected=None),
    ParseCase(name="empty", value="", expected=None),
    ParseCase(name="no_separator", value="feature-branch", expected=None),
    ParseCase(name="unknown_state", value="feature-branch::BOGUS", expected=None),
    ParseCase(name="missing_branch", value="::MERGING", expected=None),
]


@pytest.mark.parametrize("case", PARSE_CASES, ids=[c.name for c in PARSE_CASES])
async def test_get_parses_cache_value(case: ParseCase) -> None:
    cache = MemoryCache()
    if case.value is not None:
        cache.storage[MERGE_PROTECTED_CACHE_KEY] = case.value
    assert await MergeWriteBlocker(cache=cache).get() == case.expected


async def test_set_writes_expected_value() -> None:
    cache = MemoryCache()
    await MergeWriteBlocker(cache=cache).set(branch="my-branch", state=MergeProtectionState.MERGE_FAILED)
    assert cache.storage[MERGE_PROTECTED_CACHE_KEY] == "my-branch::MERGE_FAILED"


async def test_set_get_delete_round_trip() -> None:
    blocker = MergeWriteBlocker(cache=MemoryCache())
    assert await blocker.get() is None

    await blocker.set(branch="feature-branch", state=MergeProtectionState.MERGING)
    assert await blocker.get() == MergeProtection(branch="feature-branch", state=MergeProtectionState.MERGING)

    await blocker.set(branch="feature-branch", state=MergeProtectionState.MERGE_FAILED)
    assert await blocker.get() == MergeProtection(branch="feature-branch", state=MergeProtectionState.MERGE_FAILED)

    await blocker.delete()
    assert await blocker.get() is None
