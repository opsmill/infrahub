from __future__ import annotations

import pytest
from infrahub_sdk.diff import NodeDiff, NodeDiffElement, NodeDiffPeer, NodeDiffSummary

from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.merge.diff_summary_cache import MergeDiffSummaryCache
from infrahub.exceptions import ResourceNotFoundError
from tests.adapters.cache import MemoryCache


def _summary() -> list[NodeDiff]:
    attribute = NodeDiffElement(
        name="name", element_type="ATTRIBUTE", action="UPDATED", summary=NodeDiffSummary(added=0, updated=1, removed=0)
    )
    relationship = NodeDiffElement(
        name="members",
        element_type="RELATIONSHIP_MANY",
        action="UPDATED",
        summary=NodeDiffSummary(added=1, updated=0, removed=0),
        peers=[NodeDiffPeer(action="ADDED", summary=NodeDiffSummary(added=1, updated=0, removed=0))],
    )
    return [
        NodeDiff(
            branch="main",
            kind="TestDevice",
            id="n1",
            action="UPDATED",
            display_label="dev1",
            elements=[attribute, relationship],
        ),
    ]


async def test_round_trip() -> None:
    cache = MergeDiffSummaryCache(cache=MemoryCache(), serializer=DiffSummarySerializer())
    summary = _summary()
    await cache.set(diff_id="diff-1", diff_summary=summary)
    assert await cache.get(diff_id="diff-1") == summary


async def test_miss_raises() -> None:
    cache = MergeDiffSummaryCache(cache=MemoryCache(), serializer=DiffSummarySerializer())
    with pytest.raises(ResourceNotFoundError, match=r"^Merge diff summary for diff absent was not found in the cache$"):
        await cache.get(diff_id="absent")


async def test_malformed_payload_raises() -> None:
    memory = MemoryCache()
    memory.storage["branch_merge:diff_id:corrupt:diff_summary"] = "{not-valid-json"
    with pytest.raises(
        ResourceNotFoundError, match=r"^Merge diff summary for diff corrupt could not be loaded from the cache$"
    ):
        await MergeDiffSummaryCache(cache=memory, serializer=DiffSummarySerializer()).get(diff_id="corrupt")


async def test_wrong_shape_raises() -> None:
    # Valid JSON but not a list of node diffs must still normalize to the single fallback exception,
    # not pass the cast and raise deep inside the selection predicates.
    memory = MemoryCache()
    memory.storage["branch_merge:diff_id:wrong:diff_summary"] = '[{"unexpected": "shape"}]'
    with pytest.raises(
        ResourceNotFoundError, match=r"^Merge diff summary for diff wrong could not be loaded from the cache$"
    ):
        await MergeDiffSummaryCache(cache=memory, serializer=DiffSummarySerializer()).get(diff_id="wrong")
