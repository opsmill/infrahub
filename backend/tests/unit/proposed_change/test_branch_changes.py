from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, RelationshipCardinality
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.timestamp import Timestamp
from infrahub.proposed_change.branch_changes import BranchChanges, BranchChangesReader, BranchDiffWindow
from tests.adapters.cache import MemoryCache
from tests.helpers.diff_factories import (
    EnrichedNodeFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)

if TYPE_CHECKING:
    from infrahub.core.diff.model.path import EnrichedDiffRoot

PIPELINE_ID = UUID("00000000-0000-0000-0000-000000000001")
WINDOW = BranchDiffWindow(
    from_time=datetime(2026, 11, 16, 10, 0, tzinfo=UTC), to_time=datetime(2026, 11, 16, 11, 0, tzinfo=UTC)
)
CHANGED_AT = Timestamp("2026-11-16T10:30:00Z")


class _RecordingWindowDiffCoordinator(DiffCoordinator):
    """Returns a diff where a group gained one member, recording each requested window."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, str, str, bool]] = []

    async def calculate_arbitrary_timeframe_diff(  # noqa: PLR0913, PLR0917
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        node_kinds: list[str] | None = None,
        node_uuids: set[str] | None = None,
        include_unchanged: bool = False,
    ) -> EnrichedDiffRoot:
        self.requests.append(
            (base_branch.name, diff_branch.name, from_time.to_string(), to_time.to_string(), include_unchanged)
        )
        members = EnrichedRelationshipGroupFactory.build(
            name="members",
            action=DiffAction.UPDATED,
            cardinality=RelationshipCardinality.MANY,
            changed_at=CHANGED_AT,
            relationships={
                EnrichedRelationshipElementFactory.build(
                    peer_id="device-1", action=DiffAction.ADDED, changed_at=CHANGED_AT
                )
            },
        )
        group = EnrichedNodeFactory.build(
            uuid="group-1",
            kind="CoreStandardGroup",
            label="group",
            action=DiffAction.UPDATED,
            changed_at=CHANGED_AT,
            attributes=set(),
            relationships={members},
        )
        return EnrichedRootFactory.build(
            base_branch_name=base_branch.name, diff_branch_name=diff_branch.name, nodes={group}
        )


def _reader(coordinator: DiffCoordinator, cache: MemoryCache) -> BranchChangesReader:
    return BranchChangesReader(
        diff_coordinator=coordinator,
        serializer=DiffSummarySerializer(),
        cache=cache,
        branch=Branch(name="feature"),
        destination_branch=Branch(name="main"),
        pipeline_id=PIPELINE_ID,
    )


async def test_the_window_diff_is_calculated_once_per_pipeline_run() -> None:
    coordinator = _RecordingWindowDiffCoordinator()
    reader = _reader(coordinator=coordinator, cache=MemoryCache())

    first = await reader.read(window=WINDOW)
    second = await reader.read(window=WINDOW)

    assert coordinator.requests == [
        ("main", "feature", "2026-11-16T10:00:00.000000Z", "2026-11-16T11:00:00.000000Z", True),
    ]
    assert second == first
    assert first.peers_changed(node_id="group-1", relationship_name="members") == {"device-1"}


async def test_a_cached_entry_that_cannot_be_read_is_calculated_again() -> None:
    coordinator = _RecordingWindowDiffCoordinator()
    cache = MemoryCache()
    reader = _reader(coordinator=coordinator, cache=cache)
    key = (
        f"proposed_change:pipeline:pipeline_id:{PIPELINE_ID}:branch_changes:"
        f"{WINDOW.from_time.isoformat()}:{WINDOW.to_time.isoformat()}"
    )
    cache.storage[key] = '{"diff_summary": "not a list"}'

    changes = await reader.read(window=WINDOW)

    assert len(coordinator.requests) == 1
    assert changes.peers_changed(node_id="group-1", relationship_name="members") == {"device-1"}
    assert BranchChanges.model_validate_json(cache.storage[key]) == changes
