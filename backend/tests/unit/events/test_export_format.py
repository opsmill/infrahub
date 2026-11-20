from __future__ import annotations

from datetime import UTC, datetime

from infrahub.core.changelog.models import NodeChangelog
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.events.branch_action import BranchCreatedEvent, BranchMergedEvent
from infrahub.events.export_format import (
    EXPORT_FORMAT_VERSION,
    build_export_envelope,
    get_event_node_kind,
    get_ordering_key,
    reduce_export_envelope,
)
from infrahub.events.models import EventBranchContext, EventContext, EventMeta
from infrahub.events.node_action import NodeUpdatedEvent

SOURCE = "infrahub://infrahub.example.com"
CAPTURED_AT = datetime(2026, 11, 20, 10, 15, 2, 481000, tzinfo=UTC)
CAPTURED_AT_TEXT = "2026-11-20T10:15:02.481Z"
ACCOUNT_ID = "17a8b2c1-0000-0000-0000-000000000001"


def _meta(branch_name: str) -> EventMeta:
    return EventMeta(context=EventContext(branch=EventBranchContext(name=branch_name), account_id=ACCOUNT_ID))


def _node_updated_event() -> NodeUpdatedEvent:
    return NodeUpdatedEvent(
        kind="TestingDevice",
        node_id="node-1",
        changelog=NodeChangelog(node_id="node-1", node_kind="TestingDevice", display_label="device-1"),
        fields=["description"],
        meta=_meta(branch_name="main"),
    )


def _branch_merged_event() -> BranchMergedEvent:
    return BranchMergedEvent(branch_name="feature", branch_id="branch-1", meta=_meta(branch_name="feature"))


def _branch_created_event() -> BranchCreatedEvent:
    return BranchCreatedEvent(
        branch_name="feature", branch_id="branch-1", sync_with_git=False, meta=_meta(branch_name=GLOBAL_BRANCH_NAME)
    )


def test_node_event_envelope() -> None:
    event = _node_updated_event()

    envelope = build_export_envelope(event=event, source=SOURCE, captured_at=CAPTURED_AT)

    assert {key: value for key, value in envelope.items() if key != "data"} == {
        "specversion": "1.0",
        "id": str(event.meta.id),
        "source": SOURCE,
        "type": "infrahub.node.updated",
        "time": CAPTURED_AT_TEXT,
        "subject": "node-1",
        "datacontenttype": "application/json",
        "infrahubformatversion": EXPORT_FORMAT_VERSION,
        "infrahubbranch": "main",
        "infrahubnodekind": "TestingDevice",
    }


def test_node_event_data_is_the_webhook_body() -> None:
    event = _node_updated_event()

    envelope = build_export_envelope(event=event, source=SOURCE, captured_at=CAPTURED_AT)

    assert envelope["data"] == {
        "event": "infrahub.node.updated",
        "id": str(event.meta.id),
        "branch": "main",
        "account_id": ACCOUNT_ID,
        "occured_at": CAPTURED_AT_TEXT,
        "data": {
            "kind": "TestingDevice",
            "node_id": "node-1",
            "action": "updated",
            "changelog": {
                "node_id": "node-1",
                "node_kind": "TestingDevice",
                "display_label": "device-1",
                "hfid": None,
                "attributes": {},
                "relationships": {},
            },
            "fields": ["description"],
        },
    }


def test_branch_merged_envelope() -> None:
    event = _branch_merged_event()

    envelope = build_export_envelope(event=event, source=SOURCE, captured_at=CAPTURED_AT)

    assert envelope["type"] == "infrahub.branch.merged"
    assert envelope["subject"] == "feature"
    assert envelope["infrahubbranch"] == "feature"
    assert "infrahubnodekind" not in envelope
    assert envelope["data"]["branch"] == "feature"
    assert envelope["data"]["data"] == {"branch_name": "feature", "branch_id": "branch-1", "proposed_change_id": None}


def test_global_branch_event_envelope() -> None:
    event = _branch_created_event()

    envelope = build_export_envelope(event=event, source=SOURCE, captured_at=CAPTURED_AT)

    assert envelope["type"] == "infrahub.branch.created"
    assert envelope["subject"] == GLOBAL_BRANCH_NAME
    assert envelope["infrahubbranch"] == GLOBAL_BRANCH_NAME
    assert "infrahubnodekind" not in envelope
    # The webhook body reports no branch for events that apply to the whole instance.
    assert envelope["data"]["branch"] is None


def test_reduced_envelope_keeps_only_the_event_context() -> None:
    envelope = build_export_envelope(event=_node_updated_event(), source=SOURCE, captured_at=CAPTURED_AT)

    reduced = reduce_export_envelope(envelope=envelope)

    assert reduced["infrahubreduced"] is True
    assert {key: value for key, value in reduced.items() if key not in {"data", "infrahubreduced"}} == {
        key: value for key, value in envelope.items() if key != "data"
    }
    assert reduced["data"] == {
        "event": "infrahub.node.updated",
        "id": envelope["id"],
        "branch": "main",
        "account_id": ACCOUNT_ID,
        "occured_at": CAPTURED_AT_TEXT,
    }
    assert "infrahubreduced" not in envelope
    assert "changelog" in envelope["data"]["data"]


def test_ordering_key_is_the_node_id_for_node_events() -> None:
    assert get_ordering_key(event=_node_updated_event()) == "node-1"


def test_ordering_key_is_the_branch_name_for_other_events() -> None:
    assert get_ordering_key(event=_branch_merged_event()) == "feature"
    assert get_ordering_key(event=_branch_created_event()) == GLOBAL_BRANCH_NAME


def test_node_kind_is_only_set_for_node_events() -> None:
    assert get_event_node_kind(event=_node_updated_event()) == "TestingDevice"
    assert get_event_node_kind(event=_branch_merged_event()) is None
