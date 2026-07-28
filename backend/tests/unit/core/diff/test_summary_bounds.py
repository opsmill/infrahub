from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import DiffAction
from infrahub.core.diff.summary_bounds import (
    BoundedDiffSummaryBuilder,
    OversizedDiffSummary,
    SerializedDiffSummary,
)

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.diff.model.path import EnrichedDiffRoot


@dataclass
class _FakeNode:
    action: DiffAction


@dataclass
class _FakeRoot:
    """Stands in for an EnrichedDiffRoot: the builder only reads ``nodes`` and each node's action."""

    nodes: list[_FakeNode]


class _RecordingSerializer:
    """A DiffSummarySerializer double returning a fixed payload and recording that it serialized."""

    def __init__(self, payload: str) -> None:
        self._payload = payload
        self.serialize_calls = 0

    def serialize(self, *, root: EnrichedDiffRoot, target_branch_name: str) -> list[NodeDiff]:
        self.serialize_calls += 1
        return [{"kind": "TestThing", "id": "n1"}]  # type: ignore[list-item]

    def dump(self, diff_summary: list[NodeDiff]) -> str:
        return self._payload


def _root(*, changed: int, unchanged: int) -> _FakeRoot:
    return _FakeRoot(
        nodes=[_FakeNode(action=DiffAction.UPDATED) for _ in range(changed)]
        + [_FakeNode(action=DiffAction.UNCHANGED) for _ in range(unchanged)]
    )


@dataclass(frozen=True, kw_only=True)
class BoundsCase:
    name: str
    changed: int
    unchanged: int = 0
    max_nodes: int
    max_bytes: int
    payload: str = "[]"
    expect_cacheable: bool
    expected_node_count: int
    expected_byte_size: int | None
    expected_serialize_calls: int


BOUNDS_CASES = [
    BoundsCase(
        name="node_count_over_ceiling_rejected_before_serialization",
        changed=3,
        unchanged=5,
        max_nodes=2,
        max_bytes=1000,
        expect_cacheable=False,
        expected_node_count=3,
        expected_byte_size=None,
        expected_serialize_calls=0,
    ),
    BoundsCase(
        name="payload_over_byte_ceiling_rejected_after_serialization",
        changed=1,
        max_nodes=10,
        max_bytes=10,
        payload="x" * 50,
        expect_cacheable=False,
        expected_node_count=1,
        expected_byte_size=50,
        expected_serialize_calls=1,
    ),
    BoundsCase(
        name="within_both_ceilings_is_cacheable",
        changed=2,
        unchanged=4,
        max_nodes=10,
        max_bytes=100,
        payload="[]",
        expect_cacheable=True,
        expected_node_count=2,
        expected_byte_size=2,
        expected_serialize_calls=1,
    ),
]


@pytest.mark.parametrize("case", BOUNDS_CASES, ids=lambda case: case.name)
def test_bounded_diff_summary_builder(case: BoundsCase) -> None:
    serializer = _RecordingSerializer(payload=case.payload)
    builder = BoundedDiffSummaryBuilder(serializer=serializer, max_nodes=case.max_nodes, max_bytes=case.max_bytes)

    result = builder.build(root=_root(changed=case.changed, unchanged=case.unchanged), target_branch_name="main")

    assert serializer.serialize_calls == case.expected_serialize_calls
    if case.expect_cacheable:
        assert result == SerializedDiffSummary(
            diff_summary=[{"kind": "TestThing", "id": "n1"}],
            payload=case.payload,
            node_count=case.expected_node_count,
            byte_size=case.expected_byte_size,
        )
    else:
        assert result == OversizedDiffSummary(
            node_count=case.expected_node_count, byte_size=case.expected_byte_size
        )
