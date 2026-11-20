"""Build the CloudEvents 1.0 envelope (JSON structured mode) used to export events to external systems."""

from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING, Any

from pydantic_core import to_jsonable_python

from infrahub.webhook.models import EventContext

if TYPE_CHECKING:
    from datetime import datetime

    from infrahub.events.models import InfrahubEvent

EXPORT_FORMAT_VERSION = "1"
CLOUDEVENTS_SPEC_VERSION = "1.0"
EXPORT_DATA_CONTENT_TYPE = "application/json"
REDUCED_DATA_FIELDS = frozenset(EventContext.model_fields)


def _format_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def get_event_node_kind(event: InfrahubEvent) -> str | None:
    """Return the kind of the node the event is about, or None when the event is not a node event."""
    if not event.infrahub_node_kind_event:
        return None
    return event.get_resource().get("infrahub.node.kind")


def get_ordering_key(event: InfrahubEvent) -> str:
    """Return the key that keeps related events in order: the node ID for node events, otherwise the branch name."""
    if event.infrahub_node_kind_event:
        node_id = event.get_resource().get("infrahub.node.id")
        if node_id:
            return node_id
    return event.meta.context.branch.name


def build_export_envelope(event: InfrahubEvent, source: str, captured_at: datetime) -> dict[str, Any]:
    """Return the full export message for the event; `data` holds the same body a standard webhook sends."""
    occured_at = _format_time(captured_at)
    payload = to_jsonable_python(event.get_event_payload())
    context = EventContext.from_event(
        event_id=event.get_id(), event_type=event.event_name, event_occured_at=occured_at, event_payload=payload
    )

    envelope: dict[str, Any] = {
        "specversion": CLOUDEVENTS_SPEC_VERSION,
        "id": event.get_id(),
        "source": source,
        "type": event.event_name,
        "time": occured_at,
        "subject": get_ordering_key(event=event),
        "datacontenttype": EXPORT_DATA_CONTENT_TYPE,
        "infrahubformatversion": EXPORT_FORMAT_VERSION,
        "infrahubbranch": event.meta.context.branch.name,
    }
    node_kind = get_event_node_kind(event=event)
    if node_kind:
        envelope["infrahubnodekind"] = node_kind
    envelope["data"] = {"data": payload["data"], **context.model_dump()}
    return envelope


def reduce_export_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the envelope whose `data` keeps only the event context, for messages over a size limit."""
    reduced = {key: value for key, value in envelope.items() if key != "data"}
    reduced["infrahubreduced"] = True
    reduced["data"] = {key: value for key, value in envelope["data"].items() if key in REDUCED_DATA_FIELDS}
    return reduced
