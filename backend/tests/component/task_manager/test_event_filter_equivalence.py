from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest
from prefect.client.orchestration import PrefectClient, get_client
from tests.helpers.event_filters import LabelEventFilter, filter_event_ids
from tests.helpers.task_manager_seed import seed_infrahub_event

from infrahub.core.changelog.models import NodeChangelog
from infrahub.core.constants import AccountType, InfrahubKind
from infrahub.events.account_action import AccountLoggedInEvent, AuthMethod
from infrahub.events.artifact_action import ArtifactCreatedEvent, ArtifactUpdatedEvent
from infrahub.events.branch_action import BranchDeletedEvent, BranchMergedEvent, BranchMigratedEvent, BranchRebasedEvent
from infrahub.events.constants import EventSortOrder
from infrahub.events.group_action import GroupAutoCreatedEvent, GroupAutoCreateRejectedEvent
from infrahub.events.models import EventBranchContext, EventContext, EventMeta, InfrahubEvent
from infrahub.events.node_action import NodeCreatedEvent, NodeUpdatedEvent
from infrahub.events.proposed_change_action import ProposedChangeApprovedEvent, ProposedChangeMergedEvent
from infrahub.external_protocols import ExternalAuthProtocol
from infrahub.task_manager.event.models import InfrahubEventFilter
from infrahub.task_manager.event.query import PrefectEvent

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

RETENTION = timedelta(days=400)
SUFFIX = uuid4().hex[:8]

ACCOUNT_A = str(uuid4())
ACCOUNT_B = str(uuid4())
OTHER_BRANCH = (f"eq-other-{SUFFIX}", str(uuid4()))
LIVE_BRANCH = (f"eq-live-{SUFFIX}", str(uuid4()))
DELETED_BRANCH = (f"eq-deleted-{SUFFIX}", str(uuid4()))
RECREATED_NAME = f"eq-recreated-{SUFFIX}"
RECREATED_OLD_ID = str(uuid4())
RECREATED_NEW_ID = str(uuid4())
TWICE_DELETED_NAME = f"eq-twice-{SUFFIX}"
TWICE_DELETED_FIRST_ID = str(uuid4())
TWICE_DELETED_SECOND_ID = str(uuid4())
EXPIRED_BRANCH = (f"eq-expired-{SUFFIX}", str(uuid4()))
UNKNOWN_BRANCH_NAME = f"eq-unknown-{SUFFIX}"
MERGED_BRANCH = (f"eq-merged-{SUFFIX}", str(uuid4()))
NODE_ID = str(uuid4())
ARTIFACT_ID = str(uuid4())
ACCOUNT_NODE_ID = str(uuid4())
PROPOSED_CHANGE_ID = str(uuid4())
GROUP_ID = uuid4()
PARENT_ID = uuid4()
CHILD_ID = uuid4()

PROPOSED_CHANGE_TIMELINE_EVENTS = [
    "infrahub.proposed_change.merged",
    "infrahub.proposed_change.review_requested",
    "infrahub.proposed_change.approved",
    "infrahub.proposed_change.rejected",
    "infrahub.proposed_change.approval_revoked",
    "infrahub.proposed_change.rejection_revoked",
    "infrahub.proposed_change.comment",
    "infrahub.proposed_change_thread.created",
    "infrahub.proposed_change.approvals_revoked",
    "infrahub.branch.merged",
    "infrahub.branch.deleted",
]


def _meta(branch: tuple[str, str], account_id: str = ACCOUNT_B, event_id: UUID | None = None) -> EventMeta:
    name, branch_id = branch
    meta = EventMeta(context=EventContext(branch=EventBranchContext(name=name, id=branch_id), account_id=account_id))
    if event_id:
        meta.id = event_id
    return meta


def _node_updated(meta: EventMeta, node_id: str | None = None, kind: str = "TestingNode") -> NodeUpdatedEvent:
    node_id = node_id or str(uuid4())
    return NodeUpdatedEvent(
        kind=kind,
        node_id=node_id,
        changelog=NodeChangelog(node_id=node_id, node_kind=kind, display_label=node_id),
        fields=["name"],
        meta=meta,
    )


def _node_created(meta: EventMeta, node_id: str, kind: str) -> NodeCreatedEvent:
    return NodeCreatedEvent(
        kind=kind,
        node_id=node_id,
        changelog=NodeChangelog(node_id=node_id, node_kind=kind, display_label=node_id),
        fields=["name"],
        meta=meta,
    )


def _artifact(event_class: type[ArtifactCreatedEvent | ArtifactUpdatedEvent], meta: EventMeta) -> InfrahubEvent:
    return event_class(
        node_id=ARTIFACT_ID,
        artifact_definition_id=str(uuid4()),
        artifact_definition_name="startup-config",
        target_id=str(uuid4()),
        target_kind="TestingDevice",
        checksum="abc",
        storage_id=str(uuid4()),
        meta=meta,
    )


def _branch_deleted(branch: tuple[str, str], proposed_change_id: str | None = None) -> BranchDeletedEvent:
    return BranchDeletedEvent(
        branch_name=branch[0],
        branch_id=branch[1],
        sync_with_git=False,
        proposed_change_id=proposed_change_id,
        meta=_meta(OTHER_BRANCH),
    )


def _proposed_change_merged() -> ProposedChangeMergedEvent:
    return ProposedChangeMergedEvent(
        proposed_change_id=PROPOSED_CHANGE_ID,
        proposed_change_name="change",
        proposed_change_state="merged",
        merged_by_account_id=ACCOUNT_B,
        merged_by_account_name="bob",
        meta=_meta(OTHER_BRANCH),
    )


def _proposed_change_approved() -> ProposedChangeApprovedEvent:
    return ProposedChangeApprovedEvent(
        proposed_change_id=PROPOSED_CHANGE_ID,
        proposed_change_name="change",
        proposed_change_state="open",
        reviewer_account_id=ACCOUNT_B,
        reviewer_account_name="bob",
        reviewer_decision="approved",
        meta=_meta(OTHER_BRANCH),
    )


def _account_logged_in() -> AccountLoggedInEvent:
    return AccountLoggedInEvent(
        kind=InfrahubKind.ACCOUNT,
        account_id=ACCOUNT_NODE_ID,
        account_name="carol",
        account_type=AccountType.USER,
        auth_method=AuthMethod.PASSWORD,
        session_id=str(uuid4()),
        meta=_meta(OTHER_BRANCH, account_id=ACCOUNT_NODE_ID),
    )


def _group_auto_created() -> GroupAutoCreatedEvent:
    return GroupAutoCreatedEvent(
        idp="provider1",
        triggering_user_id=uuid4(),
        triggering_user_name="dave",
        protocol=ExternalAuthProtocol.OIDC,
        group_id=GROUP_ID,
        group_name="ops-admins",
        source_pattern=r"^(?P<name>ops-.*)$",
        origin_value="provider1",
        meta=_meta(OTHER_BRANCH),
    )


def _group_auto_create_rejected() -> GroupAutoCreateRejectedEvent:
    return GroupAutoCreateRejectedEvent(
        idp="provider1",
        triggering_user_id=UUID(ACCOUNT_NODE_ID),
        triggering_user_name="carol",
        protocol=ExternalAuthProtocol.OIDC,
        rejected_claim_value="bad name",
        meta=_meta(OTHER_BRANCH, account_id=ACCOUNT_NODE_ID),
    )


def _parent_events() -> dict[str, tuple[InfrahubEvent, timedelta]]:
    parent = _node_updated(meta=_meta(OTHER_BRANCH, event_id=PARENT_ID))
    first_child = _node_updated(meta=EventMeta.from_parent(parent=parent))
    first_child.meta.id = CHILD_ID
    second_child = _node_updated(meta=EventMeta.from_parent(parent=parent))
    third_child = _node_updated(meta=EventMeta.from_parent(parent=parent))
    grandchild = _node_updated(meta=EventMeta.from_parent(parent=first_child))
    return {
        "parent": (parent, timedelta(days=4)),
        "child_1": (first_child, timedelta(minutes=30)),
        "child_2": (second_child, timedelta(hours=5)),
        "child_3": (third_child, timedelta(days=3)),
        "grandchild": (grandchild, timedelta(minutes=20)),
    }


def _seeded_events() -> dict[str, tuple[InfrahubEvent, timedelta]]:
    return {
        "account_a_1": (_node_updated(meta=_meta(OTHER_BRANCH, account_id=ACCOUNT_A)), timedelta(minutes=5)),
        "account_a_2": (_node_updated(meta=_meta(OTHER_BRANCH, account_id=ACCOUNT_A)), timedelta(hours=3)),
        "account_a_3": (_node_updated(meta=_meta(OTHER_BRANCH, account_id=ACCOUNT_A)), timedelta(days=10)),
        "account_a_4": (_node_updated(meta=_meta(OTHER_BRANCH, account_id=ACCOUNT_A)), timedelta(days=200)),
        "account_b_other_branch": (_node_updated(meta=_meta(OTHER_BRANCH)), timedelta(minutes=20)),
        "live_1": (_node_updated(meta=_meta(LIVE_BRANCH)), timedelta(minutes=10)),
        "live_2": (_node_updated(meta=_meta(LIVE_BRANCH)), timedelta(hours=5)),
        "live_3": (_node_updated(meta=_meta(LIVE_BRANCH)), timedelta(days=3)),
        "live_4": (_node_updated(meta=_meta(LIVE_BRANCH)), timedelta(days=250)),
        "deleted_1": (_node_updated(meta=_meta(DELETED_BRANCH)), timedelta(minutes=40)),
        "deleted_2": (_node_updated(meta=_meta(DELETED_BRANCH)), timedelta(days=2)),
        "deleted_3": (_node_updated(meta=_meta(DELETED_BRANCH)), timedelta(days=190)),
        "deleted_branch_deleted": (_branch_deleted(DELETED_BRANCH), timedelta(minutes=35)),
        "recreated_old_1": (_node_updated(meta=_meta((RECREATED_NAME, RECREATED_OLD_ID))), timedelta(days=100)),
        "recreated_old_2": (_node_updated(meta=_meta((RECREATED_NAME, RECREATED_OLD_ID))), timedelta(days=20)),
        "recreated_deleted": (_branch_deleted((RECREATED_NAME, RECREATED_OLD_ID)), timedelta(days=1)),
        "recreated_new_1": (_node_updated(meta=_meta((RECREATED_NAME, RECREATED_NEW_ID))), timedelta(minutes=50)),
        "recreated_new_2": (_node_updated(meta=_meta((RECREATED_NAME, RECREATED_NEW_ID))), timedelta(hours=6)),
        "twice_first": (_node_updated(meta=_meta((TWICE_DELETED_NAME, TWICE_DELETED_FIRST_ID))), timedelta(days=6)),
        "twice_first_deleted": (
            _branch_deleted((TWICE_DELETED_NAME, TWICE_DELETED_FIRST_ID)),
            timedelta(days=5),
        ),
        "twice_second": (_node_updated(meta=_meta((TWICE_DELETED_NAME, TWICE_DELETED_SECOND_ID))), timedelta(days=3)),
        "twice_second_deleted": (
            _branch_deleted((TWICE_DELETED_NAME, TWICE_DELETED_SECOND_ID)),
            timedelta(days=2),
        ),
        "expired": (_node_updated(meta=_meta(EXPIRED_BRANCH)), timedelta(days=31)),
        "expired_deleted": (_branch_deleted(EXPIRED_BRANCH), timedelta(days=30)),
        "node_1": (_node_updated(meta=_meta(OTHER_BRANCH), node_id=NODE_ID), timedelta(minutes=25)),
        "node_2": (_node_updated(meta=_meta(OTHER_BRANCH), node_id=NODE_ID), timedelta(days=12)),
        "artifact_node_created": (
            _node_created(meta=_meta(OTHER_BRANCH), node_id=ARTIFACT_ID, kind=InfrahubKind.ARTIFACT),
            timedelta(days=13),
        ),
        "artifact_created": (_artifact(ArtifactCreatedEvent, meta=_meta(OTHER_BRANCH)), timedelta(days=12, hours=1)),
        "artifact_node_updated": (
            _node_updated(meta=_meta(OTHER_BRANCH), node_id=ARTIFACT_ID, kind=InfrahubKind.ARTIFACT),
            timedelta(minutes=35),
        ),
        "artifact_updated": (_artifact(ArtifactUpdatedEvent, meta=_meta(OTHER_BRANCH)), timedelta(hours=4)),
        "account_logged_in": (_account_logged_in(), timedelta(minutes=45)),
        "account_node_updated": (
            _node_updated(meta=_meta(OTHER_BRANCH), node_id=ACCOUNT_NODE_ID, kind=InfrahubKind.ACCOUNT),
            timedelta(days=3, hours=1),
        ),
        "account_group_rejected": (_group_auto_create_rejected(), timedelta(hours=2)),
        "proposed_change_approved": (_proposed_change_approved(), timedelta(hours=5, minutes=30)),
        "proposed_change_merged": (_proposed_change_merged(), timedelta(hours=4, minutes=10)),
        "proposed_change_branch_merged": (
            BranchMergedEvent(
                branch_name=MERGED_BRANCH[0],
                branch_id=MERGED_BRANCH[1],
                proposed_change_id=PROPOSED_CHANGE_ID,
                meta=_meta(OTHER_BRANCH),
            ),
            timedelta(hours=4),
        ),
        "proposed_change_branch_deleted": (
            _branch_deleted(MERGED_BRANCH, proposed_change_id=PROPOSED_CHANGE_ID),
            timedelta(hours=3, minutes=50),
        ),
        "group_auto_created": (_group_auto_created(), timedelta(days=1, hours=2)),
        "merged": (
            BranchMergedEvent(branch_name=MERGED_BRANCH[0], branch_id=MERGED_BRANCH[1], meta=_meta(OTHER_BRANCH)),
            timedelta(minutes=15),
        ),
        "rebased": (
            BranchRebasedEvent(branch_name=MERGED_BRANCH[0], branch_id=MERGED_BRANCH[1], meta=_meta(MERGED_BRANCH)),
            timedelta(days=2, hours=3),
        ),
        "migrated": (
            BranchMigratedEvent(branch_name=MERGED_BRANCH[0], branch_id=MERGED_BRANCH[1], meta=_meta(MERGED_BRANCH)),
            timedelta(days=40),
        ),
        "merged_branch_node_updated": (_node_updated(meta=_meta(MERGED_BRANCH)), timedelta(hours=1, minutes=30)),
        "other_merged": (
            BranchMergedEvent(branch_name=OTHER_BRANCH[0], branch_id=OTHER_BRANCH[1], meta=_meta(OTHER_BRANCH)),
            timedelta(minutes=55),
        ),
        **_parent_events(),
    }


@pytest.fixture(scope="module")
async def prefect_client(prefect_test_fixture: None) -> AsyncGenerator[PrefectClient, None]:
    async with get_client(sync_client=False) as client:
        yield client


@pytest.fixture(scope="module")
async def seeded(prefect_client: PrefectClient) -> dict[str, str]:
    now = datetime.now(UTC)
    ids: dict[str, str] = {}
    for position, (key, (event, age)) in enumerate(_seeded_events().items()):
        occurred = now - age - timedelta(milliseconds=position)
        ids[key] = str(await seed_infrahub_event(event=event, occurred=occurred))
    return ids


@dataclass
class BranchResolutionCase:
    name: str
    names: list[str]
    current_branch_ids: dict[str, str]
    expected: list[str]


BRANCH_RESOLUTION_CASES = [
    BranchResolutionCase(
        name="current_branch",
        names=[LIVE_BRANCH[0]],
        current_branch_ids={LIVE_BRANCH[0]: LIVE_BRANCH[1]},
        expected=[LIVE_BRANCH[1]],
    ),
    BranchResolutionCase(
        name="deleted_branch",
        names=[DELETED_BRANCH[0]],
        current_branch_ids={},
        expected=[DELETED_BRANCH[1]],
    ),
    BranchResolutionCase(
        name="recreated_branch",
        names=[RECREATED_NAME],
        current_branch_ids={RECREATED_NAME: RECREATED_NEW_ID},
        expected=[RECREATED_NEW_ID],
    ),
    BranchResolutionCase(
        name="name_deleted_twice",
        names=[TWICE_DELETED_NAME],
        current_branch_ids={},
        expected=[TWICE_DELETED_SECOND_ID],
    ),
    BranchResolutionCase(
        name="deletion_older_than_the_retention",
        names=[EXPIRED_BRANCH[0]],
        current_branch_ids={},
        expected=[],
    ),
    BranchResolutionCase(
        name="unknown_name",
        names=[UNKNOWN_BRANCH_NAME],
        current_branch_ids={},
        expected=[],
    ),
    BranchResolutionCase(
        name="several_names",
        names=[LIVE_BRANCH[0], UNKNOWN_BRANCH_NAME, DELETED_BRANCH[0]],
        current_branch_ids={LIVE_BRANCH[0]: LIVE_BRANCH[1]},
        expected=[LIVE_BRANCH[1], DELETED_BRANCH[1]],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in BRANCH_RESOLUTION_CASES])
async def test_branch_names_resolve_to_branch_ids(test_case: BranchResolutionCase, seeded: dict[str, str]) -> None:
    """A name resolves to its current branch, else to the newest deletion of that name inside the retention, else to nothing."""
    branch_ids = await PrefectEvent.resolve_branch_ids(
        names=test_case.names, current_branch_ids=test_case.current_branch_ids
    )

    assert branch_ids == test_case.expected


@dataclass
class FilterCase:
    name: str
    expected: set[str]
    label_expected: set[str] | None = None
    order: EventSortOrder = EventSortOrder.DESC
    account__ids: list[str] | None = None
    branches: list[str] | None = None
    current_branch_ids: dict[str, str] = field(default_factory=dict)
    primary_node__ids: list[str] | None = None
    parent__ids: list[str] | None = None
    event_type: list[str] | None = None
    event_type_filter: dict[str, Any] | None = None


FILTER_CASES = [
    FilterCase(
        name="account",
        account__ids=[ACCOUNT_A],
        expected={"account_a_1", "account_a_2", "account_a_3", "account_a_4"},
    ),
    FilterCase(
        name="current_branch",
        branches=[LIVE_BRANCH[0]],
        current_branch_ids={LIVE_BRANCH[0]: LIVE_BRANCH[1]},
        expected={"live_1", "live_2", "live_3", "live_4"},
    ),
    FilterCase(
        name="deleted_branch",
        branches=[DELETED_BRANCH[0]],
        expected={"deleted_1", "deleted_2", "deleted_3"},
    ),
    FilterCase(
        name="account_and_branch",
        account__ids=[ACCOUNT_A],
        branches=[OTHER_BRANCH[0]],
        current_branch_ids={OTHER_BRANCH[0]: OTHER_BRANCH[1]},
        expected={"account_a_1", "account_a_2", "account_a_3", "account_a_4"},
    ),
    FilterCase(
        name="recreated_branch_shows_only_the_current_branch",
        branches=[RECREATED_NAME],
        current_branch_ids={RECREATED_NAME: RECREATED_NEW_ID},
        expected={"recreated_new_1", "recreated_new_2"},
        label_expected={"recreated_old_1", "recreated_old_2", "recreated_new_1", "recreated_new_2"},
    ),
    FilterCase(
        name="name_deleted_twice_shows_only_the_newest_branch",
        branches=[TWICE_DELETED_NAME],
        expected={"twice_second"},
        label_expected={"twice_first", "twice_second"},
    ),
    FilterCase(
        name="node_and_artifact_without_event_type",
        primary_node__ids=[ARTIFACT_ID],
        expected={"artifact_node_created", "artifact_created", "artifact_node_updated", "artifact_updated"},
    ),
    FilterCase(
        name="node_and_artifact_by_resource_id",
        primary_node__ids=[ARTIFACT_ID, NODE_ID],
        event_type=[
            "infrahub.node.created",
            "infrahub.node.updated",
            "infrahub.artifact.created",
            "infrahub.artifact.updated",
        ],
        expected={
            "artifact_node_created",
            "artifact_created",
            "artifact_node_updated",
            "artifact_updated",
            "node_1",
            "node_2",
        },
    ),
    FilterCase(
        name="account_node_by_resource_id",
        primary_node__ids=[ACCOUNT_NODE_ID],
        event_type=["infrahub.account.logged_in", "infrahub.node.updated", "infrahub.group.auto_create_rejected"],
        expected={"account_logged_in", "account_node_updated"},
    ),
    FilterCase(
        name="proposed_change_timeline",
        order=EventSortOrder.ASC,
        primary_node__ids=[PROPOSED_CHANGE_ID],
        event_type=PROPOSED_CHANGE_TIMELINE_EVENTS,
        expected={
            "proposed_change_approved",
            "proposed_change_merged",
            "proposed_change_branch_merged",
            "proposed_change_branch_deleted",
        },
    ),
    FilterCase(
        name="proposed_change_by_resource_id",
        primary_node__ids=[PROPOSED_CHANGE_ID],
        event_type=["infrahub.proposed_change.approved", "infrahub.proposed_change.merged"],
        expected={"proposed_change_approved", "proposed_change_merged"},
    ),
    FilterCase(
        name="group_created_at_login",
        primary_node__ids=[str(GROUP_ID)],
        event_type=["infrahub.group.auto_created"],
        expected={"group_auto_created"},
    ),
    FilterCase(
        name="direct_children",
        parent__ids=[str(PARENT_ID)],
        expected={"child_1", "child_2", "child_3"},
    ),
    FilterCase(
        name="direct_children_of_a_child",
        parent__ids=[str(CHILD_ID)],
        expected={"grandchild"},
    ),
    FilterCase(
        name="branch_merged_by_name",
        event_type_filter={"branch_merged": {"branches": [MERGED_BRANCH[0]]}},
        expected={"merged", "proposed_change_branch_merged"},
    ),
    FilterCase(
        name="branch_merged_rebased_and_migrated_by_name",
        event_type_filter={
            "branch_merged": {"branches": [MERGED_BRANCH[0]]},
            "branch_migrated": {"branches": [MERGED_BRANCH[0]]},
            "branch_rebased": {"branches": [MERGED_BRANCH[0]]},
        },
        expected={"merged", "proposed_change_branch_merged", "rebased", "migrated"},
    ),
    FilterCase(
        name="branch_merged_by_name_with_another_event_type",
        event_type=["infrahub.node.updated"],
        event_type_filter={"branch_merged": {"branches": [MERGED_BRANCH[0]]}},
        expected={"merged", "proposed_change_branch_merged", "merged_branch_node_updated"},
    ),
]


def _copy(values: list[str] | None) -> list[str] | None:
    return list(values) if values is not None else None


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FILTER_CASES])
async def test_filter_returns_the_events_of_the_label_filter(
    test_case: FilterCase, seeded: dict[str, str], prefect_client: PrefectClient
) -> None:
    """Each resource-ID filter returns the events of the label filter, page by page, except for reused branch names."""
    branch_ids = None
    if test_case.branches:
        branch_ids = await PrefectEvent.resolve_branch_ids(
            names=test_case.branches, current_branch_ids=test_case.current_branch_ids
        )
    id_filter = InfrahubEventFilter.from_filters(
        order=test_case.order,
        account__ids=_copy(test_case.account__ids),
        branch_ids=branch_ids,
        primary_node__ids=_copy(test_case.primary_node__ids),
        parent__ids=_copy(test_case.parent__ids),
        event_type=_copy(test_case.event_type),
        event_type_filter=test_case.event_type_filter,
    )
    label_filter = LabelEventFilter.from_label_filters(
        order=test_case.order,
        account__ids=_copy(test_case.account__ids),
        branches=_copy(test_case.branches),
        primary_node__ids=_copy(test_case.primary_node__ids),
        parent__ids=_copy(test_case.parent__ids),
        event_type=_copy(test_case.event_type),
        event_type_filter=test_case.event_type_filter,
    )

    id_events = await filter_event_ids(client=prefect_client, event_filter=id_filter, retention=RETENTION)
    label_events = await filter_event_ids(client=prefect_client, event_filter=label_filter, retention=RETENTION)

    assert set(id_events) == {seeded[key] for key in test_case.expected}
    label_expected = test_case.label_expected if test_case.label_expected is not None else test_case.expected
    assert set(label_events) == {seeded[key] for key in label_expected}
    if test_case.label_expected is None:
        assert id_events == label_events
        for offset in (0, 2):
            id_page = await filter_event_ids(
                client=prefect_client, event_filter=id_filter, limit=2, offset=offset, retention=RETENTION
            )
            label_page = await filter_event_ids(
                client=prefect_client, event_filter=label_filter, limit=2, offset=offset, retention=RETENTION
            )
            assert id_page == label_page
            assert id_page == id_events[offset : offset + 2]
