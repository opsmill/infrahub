from datetime import UTC, datetime

from infrahub.core.constants import EventType
from infrahub.core.schema.definitions.core import core_webhook
from infrahub.events import ArtifactRenderRequestedEvent
from infrahub.events.models import EventBranchContext, EventContext, EventMeta
from infrahub.events.utils import get_all_infrahub_node_kind_events

DEADLINE = datetime(2026, 11, 20, 10, 10, tzinfo=UTC)
QUERY_RESULT = {"DcimDevice": {"edges": [{"node": {"name": {"value": "edge-01"}}}]}}


def _build_event() -> ArtifactRenderRequestedEvent:
    context = EventContext(branch=EventBranchContext(name="change-123", id="branch-uuid"), account_id="account-a")
    return ArtifactRenderRequestedEvent(
        meta=EventMeta.from_context(context=context),
        render_id="render-1",
        callback_url="https://infrahub.example.com/api/artifact/render/render-1",
        deadline=DEADLINE,
        artifact_id="artifact-1",
        artifact_name="startup-config",
        artifact_definition_id="definition-1",
        artifact_definition_name="startup-config",
        transformation_name="ansible-startup-config",
        transformation_version="1.5.0",
        content_type="text/plain",
        target_id="device-1",
        target_kind="DcimDevice",
        target_name="edge-01",
        branch="change-123",
        query_result=QUERY_RESULT,
    )


def test_render_requested_event_name_matches_event_type() -> None:
    assert (
        ArtifactRenderRequestedEvent.event_name
        == EventType.ARTIFACT_RENDER_REQUESTED.value
        == ("infrahub.artifact.render_requested")
    )


def test_render_requested_resource_carries_artifact_target_kind_and_branch() -> None:
    event = _build_event()

    assert event.get_resource() == {
        "prefect.resource.id": "artifact-1",
        "infrahub.node.kind": "DcimDevice",
        "infrahub.node.id": "artifact-1",
        "infrahub.branch.name": "change-123",
    }


def test_render_requested_related_keeps_base_resources_and_adds_target_and_artifact() -> None:
    event = _build_event()

    related = event.get_related()

    assert related[:-2] == event.meta.get_related()
    assert related[-2:] == [
        {
            "prefect.resource.id": "device-1",
            "prefect.resource.role": "infrahub.related.node",
            "infrahub.node.kind": "DcimDevice",
        },
        {
            "prefect.resource.id": "artifact-1",
            "prefect.resource.role": "infrahub.artifact",
            "infrahub.artifact.render_id": "render-1",
            "infrahub.artifact.artifact_definition_id": "definition-1",
            "infrahub.artifact.artifact_definition_name": "startup-config",
        },
    ]


def test_render_requested_payload_contains_every_render_field() -> None:
    event = _build_event()

    payload = event.get_event_payload()

    assert payload["data"] == {
        "render_id": "render-1",
        "callback_url": "https://infrahub.example.com/api/artifact/render/render-1",
        "deadline": DEADLINE,
        "artifact_id": "artifact-1",
        "artifact_name": "startup-config",
        "artifact_definition_id": "definition-1",
        "artifact_definition_name": "startup-config",
        "transformation_name": "ansible-startup-config",
        "transformation_version": "1.5.0",
        "content_type": "text/plain",
        "target_id": "device-1",
        "target_kind": "DcimDevice",
        "target_name": "edge-01",
        "branch": "change-123",
        "query_result": QUERY_RESULT,
    }
    assert payload["context"]["branch"]["name"] == "change-123"


def test_render_requested_is_a_webhook_event_type_filterable_by_node_kind() -> None:
    event_type_attribute = next(attribute for attribute in core_webhook.attributes if attribute.name == "event_type")

    assert event_type_attribute.enum is not None
    assert "infrahub.artifact.render_requested" in event_type_attribute.enum
    assert "infrahub.artifact.render_requested" in get_all_infrahub_node_kind_events()
