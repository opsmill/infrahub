from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
import textwrap
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

import infrahub.events
from infrahub.events.constants import EventSortOrder
from infrahub.events.utils import get_all_events
from infrahub.task_manager.event.models import PRIMARY_NODE_OUTSIDE_RESOURCE_EVENTS, InfrahubEventFilter

if TYPE_CHECKING:
    from infrahub.events.models import InfrahubEvent


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


def _event(event_filter: InfrahubEventFilter) -> dict[str, Any]:
    assert event_filter.event is not None
    return event_filter.event.model_dump(mode="json", exclude_none=True)


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


NODE_RESOURCE_IDS = ["infrahub.node.n1", "n1", "infrahub.account.n1", "infrahub.proposed_change.n1"]
EVENTS_WITH_THE_NODE_IN_A_LABEL = ["infrahub.branch.deleted", "infrahub.branch.merged", "infrahub.group.auto_created"]
EVENTS_WITH_THE_NODE_IN_THE_RESOURCE_ID = [
    "infrahub.account.logged_in",
    "infrahub.account.logged_out",
    "infrahub.artifact.created",
    "infrahub.artifact.updated",
    "infrahub.group.member_added",
    "infrahub.group.member_removed",
    "infrahub.node.created",
    "infrahub.node.deleted",
    "infrahub.node.updated",
    "infrahub.proposed_change.approval_revoked",
    "infrahub.proposed_change.approvals_revoked",
    "infrahub.proposed_change.approved",
    "infrahub.proposed_change.merged",
    "infrahub.proposed_change.rejected",
    "infrahub.proposed_change.rejection_revoked",
    "infrahub.proposed_change.review_requested",
    "infrahub.proposed_change_thread.created",
    "infrahub.proposed_change_thread.updated",
    "infrahub.validator.failed",
    "infrahub.validator.passed",
    "infrahub.validator.started",
]


@dataclass
class PrimaryNodeFilterCase:
    name: str
    event_type: list[str] | None
    expected: list[tuple[dict[str, Any], dict[str, Any]]]
    exclude_prefixes: list[str] | None = None
    event_type_filter: dict[str, Any] | None = None


PRIMARY_NODE_FILTER_CASES = [
    PrimaryNodeFilterCase(
        name="event_types_whose_resource_id_holds_the_node_id",
        event_type=["infrahub.node.updated", "infrahub.artifact.updated"],
        expected=[
            (
                {"name": ["infrahub.node.updated", "infrahub.artifact.updated"]},
                {"labels": {"prefect.resource.id": NODE_RESOURCE_IDS, "infrahub.node.id": ["n1"]}, "distinct": False},
            )
        ],
    ),
    PrimaryNodeFilterCase(
        name="no_event_type",
        event_type=None,
        expected=[
            (
                {"prefix": ["infrahub."], "exclude_name": EVENTS_WITH_THE_NODE_IN_A_LABEL},
                {"labels": {"prefect.resource.id": NODE_RESOURCE_IDS, "infrahub.node.id": ["n1"]}, "distinct": False},
            ),
            (
                {"name": EVENTS_WITH_THE_NODE_IN_A_LABEL},
                {"labels": {"infrahub.node.id": ["n1"]}, "distinct": False},
            ),
        ],
    ),
    PrimaryNodeFilterCase(
        name="no_event_type_without_the_account_events",
        event_type=None,
        exclude_prefixes=["infrahub.account."],
        expected=[
            (
                {
                    "prefix": ["infrahub."],
                    "exclude_prefix": ["infrahub.account."],
                    "exclude_name": EVENTS_WITH_THE_NODE_IN_A_LABEL,
                },
                {"labels": {"prefect.resource.id": NODE_RESOURCE_IDS, "infrahub.node.id": ["n1"]}, "distinct": False},
            ),
            (
                {"name": EVENTS_WITH_THE_NODE_IN_A_LABEL},
                {"labels": {"infrahub.node.id": ["n1"]}, "distinct": False},
            ),
        ],
    ),
    PrimaryNodeFilterCase(
        name="branch_event_carrying_a_proposed_change_with_another_event_type",
        event_type=["infrahub.proposed_change.approved", "infrahub.branch.merged"],
        expected=[
            (
                {"name": ["infrahub.proposed_change.approved"]},
                {"labels": {"prefect.resource.id": NODE_RESOURCE_IDS, "infrahub.node.id": ["n1"]}, "distinct": False},
            ),
            (
                {"name": ["infrahub.branch.merged"]},
                {"labels": {"infrahub.node.id": ["n1"]}, "distinct": False},
            ),
        ],
    ),
    PrimaryNodeFilterCase(
        name="branch_deletion_carrying_a_proposed_change",
        event_type=["infrahub.branch.deleted"],
        expected=[({"name": ["infrahub.branch.deleted"]}, {"labels": {"infrahub.node.id": ["n1"]}, "distinct": False})],
    ),
    PrimaryNodeFilterCase(
        name="group_created_for_another_account",
        event_type=["infrahub.group.auto_created"],
        expected=[
            ({"name": ["infrahub.group.auto_created"]}, {"labels": {"infrahub.node.id": ["n1"]}, "distinct": False})
        ],
    ),
    PrimaryNodeFilterCase(
        name="branch_merged_by_name",
        event_type=None,
        event_type_filter={"branch_merged": {"branches": ["feature-x"]}},
        expected=[
            (
                {"name": ["infrahub.branch.merged"]},
                {"id": ["infrahub.branch.feature-x"], "labels": {"infrahub.node.id": ["n1"]}, "distinct": False},
            )
        ],
    ),
    PrimaryNodeFilterCase(
        name="branch_merged_by_name_with_another_event_type",
        event_type=["infrahub.node.updated"],
        event_type_filter={"branch_merged": {"branches": ["feature-x"]}},
        expected=[
            (
                {"name": ["infrahub.node.updated"]},
                {
                    "labels": {
                        "infrahub.branch.name": ["feature-x"],
                        "prefect.resource.id": NODE_RESOURCE_IDS,
                        "infrahub.node.id": ["n1"],
                    },
                    "distinct": False,
                },
            ),
            (
                {"name": ["infrahub.branch.merged"]},
                {"labels": {"infrahub.branch.name": ["feature-x"], "infrahub.node.id": ["n1"]}, "distinct": False},
            ),
        ],
    ),
    PrimaryNodeFilterCase(
        name="group_creation_by_provider_and_protocol",
        event_type=None,
        event_type_filter={"group_auto_create": {"idp": ["provider1"], "protocol": ["oidc"]}},
        expected=[
            (
                {"name": ["infrahub.group.auto_create_rejected", "infrahub.group.auto_create_capped"]},
                {
                    "labels": {
                        "infrahub.security.idp": ["provider1"],
                        "infrahub.security.protocol": ["oidc"],
                        "prefect.resource.id": NODE_RESOURCE_IDS,
                        "infrahub.node.id": ["n1"],
                    },
                    "distinct": False,
                },
            ),
            (
                {"name": ["infrahub.group.auto_created"]},
                {
                    "labels": {
                        "infrahub.security.idp": ["provider1"],
                        "infrahub.security.protocol": ["oidc"],
                        "infrahub.node.id": ["n1"],
                    },
                    "distinct": False,
                },
            ),
        ],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PRIMARY_NODE_FILTER_CASES])
def test_primary_nodes_are_matched_by_resource_id_except_for_the_events_that_keep_the_node_in_a_label(
    test_case: PrimaryNodeFilterCase,
) -> None:
    """One filter matches the indexed resource ID forms, and a second one lists the event types matched by label.

    Both keep the branch, provider and protocol conditions of the event type filter.
    """
    event_filter = InfrahubEventFilter.from_filters(
        order=EventSortOrder.DESC,
        event_type=test_case.event_type,
        event_type_filter=test_case.event_type_filter,
        exclude_prefixes=test_case.exclude_prefixes,
    )

    filters = event_filter.for_primary_nodes(primary_node__ids=["n1"])

    assert [(_event(node_filter), _resource(node_filter)) for node_filter in filters] == test_case.expected


def test_a_filter_without_a_primary_node_is_read_as_it_is() -> None:
    """Without a primary node there is one filter to read, unchanged."""
    event_filter = InfrahubEventFilter.from_filters(order=EventSortOrder.DESC, event_type=["infrahub.node.updated"])

    assert event_filter.for_primary_nodes(primary_node__ids=None) == [event_filter]


def test_the_filters_of_a_primary_node_keep_the_time_range_and_the_other_conditions() -> None:
    """Each filter of a primary node keeps the order, the time range and the account of the filter it comes from."""
    until = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
    event_filter = InfrahubEventFilter.from_filters(order=EventSortOrder.ASC, account__ids=["a1"], until=until)

    filters = event_filter.for_primary_nodes(primary_node__ids=["n1"])

    assert [
        (node_filter.order.value, node_filter.to_request()["occurred"], _related(node_filter))
        for node_filter in filters
    ] == [
        (
            "ASC",
            {"until": "2026-10-04T12:00:00Z"},
            [{"id": ["infrahub.account.a1"], "role": ["infrahub.account"]}],
        )
    ] * 2


def _node_id_expression_and_resource_id(function: ast.FunctionDef) -> tuple[str | None, str | None]:
    """Return the source of the values a `get_resource` gives the node ID label and the resource ID, when it sets them."""
    values: dict[str, str] = {}
    for node in ast.walk(function):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    values[key.value] = ast.unparse(value)
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Subscript)
            and isinstance(node.targets[0].slice, ast.Constant)
            and isinstance(node.targets[0].slice.value, str)
        ):
            values[node.targets[0].slice.value] = ast.unparse(node.value)
    return values.get("infrahub.node.id"), values.get("prefect.resource.id")


def _node_id_place(event_class: type[InfrahubEvent]) -> str | None:
    """Tell whether an event that sets a node ID label keeps that ID in its resource ID, in a form a node filter matches."""
    for klass in event_class.__mro__:
        if "get_resource" not in klass.__dict__:
            continue
        function = ast.parse(textwrap.dedent(inspect.getsource(klass.__dict__["get_resource"]))).body[0]
        assert isinstance(function, ast.FunctionDef)
        node_id, resource_id = _node_id_expression_and_resource_id(function)
        if node_id is None:
            continue
        matched_forms = {
            node_id,
            f"f'infrahub.node.{{{node_id}}}'",
            f"f'infrahub.account.{{{node_id}}}'",
            f"f'infrahub.proposed_change.{{{node_id}}}'",
        }
        return "resource_id" if resource_id in matched_forms else "label"
    return None


def test_the_events_matched_by_label_are_the_ones_that_keep_their_node_outside_the_resource_id() -> None:
    """A node filter matches every other event type by resource ID, so an event type missing from the set is not returned."""
    for module in pkgutil.iter_modules(infrahub.events.__path__):
        importlib.import_module(f"infrahub.events.{module.name}")

    event_names: dict[str, set[str]] = {"resource_id": set(), "label": set()}
    for event_class in get_all_events():
        if place := _node_id_place(event_class):
            event_names[place].add(event_class.event_name)

    assert event_names == {
        "resource_id": set(EVENTS_WITH_THE_NODE_IN_THE_RESOURCE_ID),
        "label": set(EVENTS_WITH_THE_NODE_IN_A_LABEL),
    }
    assert event_names["label"] == PRIMARY_NODE_OUTSIDE_RESOURCE_EVENTS


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
