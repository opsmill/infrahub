from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.diff import NodeDiffElement, NodeDiffPeer, NodeDiffSummary

from infrahub.core.regeneration.changes_since import DiffChangeTimes, changes_since, peers_changed_since
from tests.helpers.diff_summary import node_diff, node_diff_element

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

BEFORE = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
SINCE = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
AFTER = datetime(2026, 1, 1, 14, 0, tzinfo=UTC)

DEVICE_ID = "11111111-1111-1111-1111-111111111111"
GROUP_ID = "22222222-2222-2222-2222-222222222222"
PEER_1 = "33333333-3333-3333-3333-333333333333"
PEER_2 = "44444444-4444-4444-4444-444444444444"
PEER_3 = "55555555-5555-5555-5555-555555555555"


@dataclass(frozen=True, kw_only=True)
class ChangesSinceCase:
    name: str
    diff_summary: list[NodeDiff]
    node_times: dict[str, datetime] = field(default_factory=dict)
    field_times: dict[str, dict[str, datetime]] = field(default_factory=dict)
    expected: list[NodeDiff]


CHANGES_SINCE_CASES: list[ChangesSinceCase] = [
    ChangesSinceCase(
        name="field_changed_before_is_dropped_with_its_node",
        diff_summary=[node_diff(node_id=DEVICE_ID, kind="TestDevice", field_names=["name"])],
        node_times={DEVICE_ID: BEFORE},
        field_times={DEVICE_ID: {"name": BEFORE}},
        expected=[],
    ),
    ChangesSinceCase(
        name="only_the_fields_changed_after_are_kept",
        diff_summary=[node_diff(node_id=DEVICE_ID, kind="TestDevice", field_names=["name", "color"])],
        node_times={DEVICE_ID: AFTER},
        field_times={DEVICE_ID: {"name": BEFORE, "color": AFTER}},
        expected=[node_diff(node_id=DEVICE_ID, kind="TestDevice", field_names=["color"])],
    ),
    ChangesSinceCase(
        name="field_changed_at_the_time_itself_is_kept",
        diff_summary=[node_diff(node_id=DEVICE_ID, kind="TestDevice", field_names=["name"])],
        node_times={DEVICE_ID: SINCE},
        field_times={DEVICE_ID: {"name": SINCE}},
        expected=[node_diff(node_id=DEVICE_ID, kind="TestDevice", field_names=["name"])],
    ),
    ChangesSinceCase(
        name="unchanged_field_changed_after_counts_as_updated",
        diff_summary=[
            node_diff(
                node_id=DEVICE_ID,
                kind="TestDevice",
                action="UNCHANGED",
                elements=[node_diff_element(name="name", action="UNCHANGED")],
            )
        ],
        node_times={DEVICE_ID: AFTER},
        field_times={DEVICE_ID: {"name": AFTER}},
        expected=[node_diff(node_id=DEVICE_ID, kind="TestDevice", action="UPDATED", field_names=["name"])],
    ),
    ChangesSinceCase(
        name="unchanged_field_changed_before_is_dropped",
        diff_summary=[
            node_diff(
                node_id=DEVICE_ID,
                kind="TestDevice",
                action="UNCHANGED",
                elements=[node_diff_element(name="name", action="UNCHANGED")],
            )
        ],
        node_times={DEVICE_ID: BEFORE},
        field_times={DEVICE_ID: {"name": BEFORE}},
        expected=[],
    ),
    ChangesSinceCase(
        name="changed_field_without_a_time_is_kept",
        diff_summary=[node_diff(node_id=DEVICE_ID, kind="TestDevice", field_names=["name"])],
        expected=[node_diff(node_id=DEVICE_ID, kind="TestDevice", field_names=["name"])],
    ),
    ChangesSinceCase(
        name="unchanged_field_without_a_time_is_dropped",
        diff_summary=[
            node_diff(
                node_id=DEVICE_ID,
                kind="TestDevice",
                action="UNCHANGED",
                elements=[node_diff_element(name="name", action="UNCHANGED")],
            )
        ],
        expected=[],
    ),
    ChangesSinceCase(
        name="node_removed_after_is_kept_without_fields",
        diff_summary=[node_diff(node_id=DEVICE_ID, kind="TestDevice", action="REMOVED")],
        node_times={DEVICE_ID: AFTER},
        expected=[node_diff(node_id=DEVICE_ID, kind="TestDevice", action="REMOVED")],
    ),
    ChangesSinceCase(
        name="node_added_before_is_dropped_without_fields",
        diff_summary=[node_diff(node_id=DEVICE_ID, kind="TestDevice", action="ADDED")],
        node_times={DEVICE_ID: BEFORE},
        expected=[],
    ),
    ChangesSinceCase(
        name="node_added_before_keeps_its_action_with_a_field_changed_after",
        diff_summary=[
            node_diff(
                node_id=DEVICE_ID,
                kind="TestDevice",
                action="ADDED",
                elements=[
                    node_diff_element(name="name", action="ADDED"),
                    node_diff_element(name="color", action="ADDED"),
                ],
            )
        ],
        node_times={DEVICE_ID: AFTER},
        field_times={DEVICE_ID: {"name": BEFORE, "color": AFTER}},
        expected=[
            node_diff(
                node_id=DEVICE_ID,
                kind="TestDevice",
                action="ADDED",
                elements=[node_diff_element(name="color", action="ADDED")],
            )
        ],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in CHANGES_SINCE_CASES])
def test_changes_since(test_case: ChangesSinceCase) -> None:
    change_times = DiffChangeTimes(
        from_time=BEFORE, to_time=AFTER, nodes=test_case.node_times, fields=test_case.field_times
    )

    recent = changes_since(diff_summary=test_case.diff_summary, change_times=change_times, since=SINCE)

    assert recent == test_case.expected


def test_changes_since_keeps_the_peers_of_a_relationship_counted_as_updated() -> None:
    peers = [NodeDiffPeer(action="UNCHANGED", summary=NodeDiffSummary(added=0, updated=0, removed=0))]
    members = NodeDiffElement(
        name="members",
        element_type="RELATIONSHIP_MANY",
        action="UNCHANGED",
        summary=NodeDiffSummary(added=0, updated=0, removed=0),
        peers=peers,
    )
    change_times = DiffChangeTimes(
        from_time=BEFORE, to_time=AFTER, nodes={GROUP_ID: AFTER}, fields={GROUP_ID: {"members": AFTER}}
    )

    recent = changes_since(
        diff_summary=[node_diff(node_id=GROUP_ID, kind="CoreStandardGroup", action="UNCHANGED", elements=[members])],
        change_times=change_times,
        since=SINCE,
    )

    assert recent == [
        node_diff(
            node_id=GROUP_ID,
            kind="CoreStandardGroup",
            action="UPDATED",
            elements=[
                NodeDiffElement(
                    name="members",
                    element_type="RELATIONSHIP_MANY",
                    action="UPDATED",
                    summary=NodeDiffSummary(added=0, updated=0, removed=0),
                    peers=peers,
                )
            ],
        )
    ]


def test_peers_changed_since_returns_the_peers_changed_at_or_after_the_time() -> None:
    change_times = DiffChangeTimes(
        from_time=BEFORE,
        to_time=AFTER,
        peers={
            GROUP_ID: {
                "members": {PEER_1: BEFORE, PEER_2: SINCE, PEER_3: AFTER},
                "subscribers": {DEVICE_ID: AFTER},
            }
        },
    )

    changed = peers_changed_since(change_times=change_times, node_id=GROUP_ID, relationship_name="members", since=SINCE)

    assert changed == {PEER_2, PEER_3}


def test_peers_changed_since_is_empty_for_a_node_outside_the_diff() -> None:
    change_times = DiffChangeTimes(from_time=BEFORE, to_time=AFTER, peers={GROUP_ID: {"members": {PEER_1: AFTER}}})

    changed = peers_changed_since(
        change_times=change_times, node_id=DEVICE_ID, relationship_name="members", since=SINCE
    )

    assert changed == set()
