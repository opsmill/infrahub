"""Ask an external engine to render an artifact by emitting a render-requested event."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub_sdk.protocols import CoreWebhook
from prefect.events import Event

from infrahub.artifacts.render_lock import artifact_render_lock
from infrahub.core import registry
from infrahub.core.constants import ArtifactStatus, EventType
from infrahub.events.artifact_action import ArtifactRenderRequestedEvent
from infrahub.events.models import EventMeta

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.protocols import CoreArtifact

    from infrahub.artifacts.models import CheckArtifactCreate
    from infrahub.events import InfrahubEvent
    from infrahub.git.models import RequestArtifactGenerate
    from infrahub.services.adapters.event import InfrahubEventService

RENDER_CALLBACK_PATH = "/api/artifact/render/{render_id}"

NO_SUBSCRIBED_WEBHOOK_MESSAGE = f"no webhook subscribed to {EventType.ARTIFACT_RENDER_REQUESTED.value}"
PUBLIC_URL_MISSING_MESSAGE = "main.public_url must be set for external transformations"
EVENT_TOO_LARGE_MESSAGE = "query result too large for a render request ({size} bytes, limit {limit})"


@dataclass(frozen=True)
class RenderRequestResult:
    render_id: str | None = None
    error: str | None = None
    """Why the artifact was set to Error without a render request being emitted."""


async def request_external_render(
    client: InfrahubClient,
    event_service: InfrahubEventService,
    artifact: CoreArtifact,
    model: RequestArtifactGenerate | CheckArtifactCreate,
    transformation_name: str,
    transformation_version: str,
    public_url: str | None,
    max_event_size_bytes: int,
) -> RenderRequestResult:
    """Run the artifact's query, mark the artifact Pending and emit one render request for an external engine.

    `public_url` is `main.public_url` and `max_event_size_bytes` is Prefect's event size limit, above which
    Prefect refuses the event. When the request cannot reach an engine, the artifact is set to Error and nothing
    is emitted.
    """
    async with artifact_render_lock(branch=model.branch_name, artifact_id=artifact.id):
        if not await _has_subscribed_webhook(
            client=client, branch_name=model.branch_name, target_kind=model.target_kind
        ):
            return await _fail(artifact=artifact, model=model, message=NO_SUBSCRIBED_WEBHOOK_MESSAGE)
        if not public_url:
            return await _fail(artifact=artifact, model=model, message=PUBLIC_URL_MISSING_MESSAGE)

        response = await client.query_gql_query(
            name=model.query_id,
            variables=model.variables,
            update_group=True,
            subscribers=[artifact.id],
            tracker="artifact-query-graphql-data",
            branch_name=model.branch_name,
            timeout=model.timeout,
        )

        render_id = str(uuid4())
        deadline = datetime.now(UTC) + timedelta(seconds=model.timeout)
        event = ArtifactRenderRequestedEvent(
            render_id=render_id,
            callback_url=public_url.rstrip("/") + RENDER_CALLBACK_PATH.format(render_id=render_id),
            deadline=deadline,
            artifact_id=artifact.id,
            artifact_name=model.artifact_name,
            artifact_definition_id=model.artifact_definition,
            artifact_definition_name=model.artifact_definition_name,
            transformation_name=transformation_name,
            transformation_version=transformation_version,
            content_type=model.content_type,
            target_id=model.target_id,
            target_kind=model.target_kind,
            target_name=model.target_name,
            branch=model.branch_name,
            query_result=response["data"],
            meta=EventMeta.from_context(
                context=model.context.to_event_context(),
                branch=registry.get_branch_from_registry(branch=model.branch_name),
            ),
        )

        size = _serialized_size(event=event)
        if size > max_event_size_bytes:
            return await _fail(
                artifact=artifact,
                model=model,
                message=EVENT_TOO_LARGE_MESSAGE.format(size=size, limit=max_event_size_bytes),
            )

        artifact.status.value = ArtifactStatus.PENDING.value
        artifact.render_request_id.value = render_id
        artifact.render_deadline.value = deadline.isoformat()
        await artifact.save(request_context=model.context.to_request_context())

        await event_service.send(event=event)
        return RenderRequestResult(render_id=render_id)


async def _has_subscribed_webhook(client: InfrahubClient, branch_name: str, target_kind: str) -> bool:
    """Return whether an active webhook subscribed to render requests receives this one.

    Only such a webhook gets a render token, so a webhook subscribed to all events does not count.
    """
    webhooks = await client.filters(
        kind=CoreWebhook,
        active__value=True,
        event_type__value=EventType.ARTIFACT_RENDER_REQUESTED.value,
        branch=registry.default_branch,
    )
    is_default_branch = branch_name == registry.default_branch
    for webhook in webhooks:
        if webhook.node_kind.value and webhook.node_kind.value != target_kind:
            continue
        match webhook.branch_scope.value:
            case "all_branches":
                return True
            case "default_branch" if is_default_branch:
                return True
            case "other_branches" if not is_default_branch:
                return True
    return False


def _serialized_size(event: InfrahubEvent) -> int:
    """Return the size Prefect measures when it checks an event against its size limit."""
    return Event(
        id=event.meta.id,
        event=event.event_name,
        resource=event.get_resource(),
        related=event.get_related(),
        payload=event.get_event_payload(),
        occurred=datetime.now(UTC),
    ).size_bytes


async def _fail(
    artifact: CoreArtifact, model: RequestArtifactGenerate | CheckArtifactCreate, message: str
) -> RenderRequestResult:
    artifact.status.value = ArtifactStatus.ERROR.value
    artifact.render_request_id.value = None
    artifact.render_deadline.value = None
    await artifact.save(request_context=model.context.to_request_context())
    return RenderRequestResult(error=message)
