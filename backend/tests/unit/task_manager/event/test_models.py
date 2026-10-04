from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from infrahub.events.constants import EventSortOrder
from infrahub.task_manager.event.models import InfrahubEventFilter


class TestInfrahubEventFilter:
    def test_add_event_type_filter_with_exclude_prefixes_only(self) -> None:
        """When only exclude_prefixes is provided, the filter should scope to the infrahub namespace prefix."""
        event_filter = InfrahubEventFilter()
        event_filter.add_event_type_filter(exclude_prefixes=["infrahub.account."])

        assert event_filter.event is not None
        assert event_filter.event.prefix == ["infrahub."]
        assert event_filter.event.exclude_prefix == ["infrahub.account."]

    def test_add_event_type_filter_with_event_type_only(self) -> None:
        """When event_type is provided, it takes priority and no prefix is set."""
        event_filter = InfrahubEventFilter()
        event_filter.add_event_type_filter(event_type=["infrahub.branch.created"])

        assert event_filter.event is not None
        assert event_filter.event.name == ["infrahub.branch.created"]
        assert not event_filter.event.prefix

    def test_add_event_type_filter_with_no_args(self) -> None:
        """When no arguments are provided, the event filter is not set."""
        event_filter = InfrahubEventFilter()
        event_filter.add_event_type_filter()

        assert event_filter.event is None


def _related(event_filter: InfrahubEventFilter) -> list[dict[str, Any]]:
    assert isinstance(event_filter.related, list)
    return [related.model_dump(mode="json", exclude_none=True) for related in event_filter.related]


def _resource(event_filter: InfrahubEventFilter) -> dict[str, Any]:
    assert event_filter.resource is not None
    return event_filter.resource.model_dump(mode="json", exclude_none=True)


def test_account_filter_matches_the_account_resource_id() -> None:
    """An account filter matches the indexed ID of the account related item."""
    event_filter = InfrahubEventFilter.from_filters(order=EventSortOrder.DESC, account__ids=["a1", "a2"])

    assert _related(event_filter) == [
        {"id": ["infrahub.account.a1", "infrahub.account.a2"], "role": ["infrahub.account"]},
    ]


def test_branch_filter_matches_the_branch_resource_id() -> None:
    """A branch filter matches the indexed ID of the branch related item, built from branch IDs."""
    event_filter = InfrahubEventFilter.from_filters(order=EventSortOrder.DESC, branch_ids=["b1", "b2"])

    assert _related(event_filter) == [
        {"id": ["infrahub.branch.b1", "infrahub.branch.b2"], "role": ["infrahub.branch"]},
    ]


def test_parent_filter_matches_the_ancestor_id_and_the_direct_parent_label() -> None:
    """A parent filter matches the indexed ancestor ID and keeps the label check that limits it to direct children."""
    event_filter = InfrahubEventFilter.from_filters(order=EventSortOrder.DESC, parent__ids=["p1"])

    assert _related(event_filter) == [
        {"id": ["p1"], "role": ["infrahub.ancestor_event"]},
        {"labels": {"prefect.resource.role": "infrahub.child_event", "infrahub.event_parent.id": ["p1"]}},
    ]


@dataclass
class PrimaryNodeFilterCase:
    name: str
    event_type: list[str] | None
    expected_resource: dict[str, Any]


PRIMARY_NODE_FILTER_CASES = [
    PrimaryNodeFilterCase(
        name="event_types_whose_resource_id_holds_the_node_id",
        event_type=["infrahub.node.updated", "infrahub.artifact.updated"],
        expected_resource={
            "labels": {
                "prefect.resource.id": [
                    "infrahub.node.n1",
                    "n1",
                    "infrahub.account.n1",
                    "infrahub.proposed_change.n1",
                ],
                "infrahub.node.id": ["n1"],
            },
            "distinct": False,
        },
    ),
    PrimaryNodeFilterCase(
        name="no_event_type",
        event_type=None,
        expected_resource={"labels": {"infrahub.node.id": ["n1"]}, "distinct": False},
    ),
    PrimaryNodeFilterCase(
        name="branch_event_carrying_a_proposed_change",
        event_type=["infrahub.proposed_change.approved", "infrahub.branch.merged"],
        expected_resource={"labels": {"infrahub.node.id": ["n1"]}, "distinct": False},
    ),
    PrimaryNodeFilterCase(
        name="branch_deletion_carrying_a_proposed_change",
        event_type=["infrahub.branch.deleted"],
        expected_resource={"labels": {"infrahub.node.id": ["n1"]}, "distinct": False},
    ),
    PrimaryNodeFilterCase(
        name="group_created_for_another_account",
        event_type=["infrahub.group.auto_created"],
        expected_resource={"labels": {"infrahub.node.id": ["n1"]}, "distinct": False},
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PRIMARY_NODE_FILTER_CASES])
def test_primary_node_filter(test_case: PrimaryNodeFilterCase) -> None:
    """A primary node filter matches the indexed resource ID forms only when every listed event type keeps the node ID in it."""
    event_filter = InfrahubEventFilter.from_filters(
        order=EventSortOrder.DESC, event_type=test_case.event_type, primary_node__ids=["n1"]
    )

    assert _resource(event_filter) == test_case.expected_resource


@dataclass
class BranchNameFilterCase:
    name: str
    event_type: list[str] | None
    event_type_filter: dict[str, Any]
    expected_event_names: list[str]
    expected_resource: dict[str, Any]


BRANCH_NAME_FILTER_CASES = [
    BranchNameFilterCase(
        name="merged",
        event_type=None,
        event_type_filter={"branch_merged": {"branches": ["feature-x"]}},
        expected_event_names=["infrahub.branch.merged"],
        expected_resource={"id": ["infrahub.branch.feature-x"], "distinct": False},
    ),
    BranchNameFilterCase(
        name="merged_rebased_and_migrated",
        event_type=None,
        event_type_filter={
            "branch_merged": {"branches": ["feature-x"]},
            "branch_migrated": {"branches": ["feature-y"]},
            "branch_rebased": {"branches": ["feature-z"]},
        },
        expected_event_names=["infrahub.branch.merged", "infrahub.branch.migrated", "infrahub.branch.rebased"],
        expected_resource={"id": ["infrahub.branch.feature-z"], "distinct": False},
    ),
    BranchNameFilterCase(
        name="with_another_event_type",
        event_type=["infrahub.node.updated"],
        event_type_filter={"branch_merged": {"branches": ["feature-x"]}},
        expected_event_names=["infrahub.node.updated", "infrahub.branch.merged"],
        expected_resource={"labels": {"infrahub.branch.name": ["feature-x"]}, "distinct": False},
    ),
    BranchNameFilterCase(
        name="with_the_group_creation_events",
        event_type=None,
        event_type_filter={"branch_rebased": {"branches": ["feature-x"]}, "group_auto_create": {}},
        expected_event_names=[
            "infrahub.branch.rebased",
            "infrahub.group.auto_created",
            "infrahub.group.auto_create_rejected",
            "infrahub.group.auto_create_capped",
        ],
        expected_resource={"labels": {"infrahub.branch.name": ["feature-x"]}, "distinct": False},
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in BRANCH_NAME_FILTER_CASES])
def test_branch_name_filter(test_case: BranchNameFilterCase) -> None:
    """A branch-name option matches the branch events' resource ID unless another event type is listed."""
    event_filter = InfrahubEventFilter.from_filters(
        order=EventSortOrder.DESC, event_type=test_case.event_type, event_type_filter=test_case.event_type_filter
    )

    assert event_filter.event is not None
    assert event_filter.event.name == test_case.expected_event_names
    assert _resource(event_filter) == test_case.expected_resource


def test_request_leaves_an_unset_start_to_the_task_manager() -> None:
    """A filter without a start sends only its end, so the task manager bounds the start by its retention."""
    until = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
    event_filter = InfrahubEventFilter.from_filters(order=EventSortOrder.DESC, until=until)

    assert event_filter.to_request()["occurred"] == {"until": "2026-10-04T12:00:00Z"}


def test_request_keeps_an_explicit_start() -> None:
    """A filter with a start sends it."""
    since = datetime(2026, 1, 1, tzinfo=UTC)
    until = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
    event_filter = InfrahubEventFilter.from_filters(order=EventSortOrder.DESC, since=since, until=until)

    assert event_filter.to_request()["occurred"] == {"since": "2026-01-01T00:00:00Z", "until": "2026-10-04T12:00:00Z"}
