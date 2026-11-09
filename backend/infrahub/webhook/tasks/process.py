from __future__ import annotations

import time
from functools import lru_cache
from typing import TYPE_CHECKING, Any
from uuid import UUID

import httpx
import ujson
from infrahub_sdk import InfrahubClient  # noqa: TC002  needed for prefect flow
from infrahub_sdk.protocols import CoreTransformPython, CoreWebhook
from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.client.orchestration import get_client as get_prefect_client
from prefect.logging import get_run_logger
from prefect.runtime import flow_run
from prefect.states import Cancelled, Failed

from infrahub.core.constants import InfrahubKind
from infrahub.events.models import EventContext as InfrahubEventContext
from infrahub.message_bus.types import KVTTL
from infrahub.task_manager.flow_run.constants import WEBHOOK_HTTP_ARTIFACT_KEY, WEBHOOK_HTTP_ARTIFACT_TYPE
from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter
from infrahub.workers.dependencies import get_cache, get_client, get_http
from infrahub.workflows.utils import add_tags

from ..capture import CapturedHttp, build_http_capture
from ..classifier import EXPECTED_DELIVERY_ERRORS, WebhookDeliveryError, WebhookFailureClassifier
from ..constants import (
    CACHE_KEY_PREFIX,
    WEBHOOK_SEND_ATTEMPTS,
    WEBHOOK_SEND_RETRIES,
    WEBHOOK_SEND_RETRY_DELAY_SECONDS,
)
from ..log_formatter import PAYLOAD_LOG_LIMIT, WebhookLogFormatter
from ..models import CustomWebhook, EventContext, HeaderKind, StandardWebhook, TransformWebhook, Webhook, WebhookHeader

if TYPE_CHECKING:
    from httpx import Response
    from infrahub_sdk.context import RequestContext
    from prefect.client.schemas.objects import State


WEBHOOK_MAP: dict[str, type[Webhook]] = {
    "StandardWebhook": StandardWebhook,
    "CustomWebhook": CustomWebhook,
    "TransformWebhook": TransformWebhook,
}


@lru_cache(maxsize=1)
def get_webhook_log_formatter() -> WebhookLogFormatter:
    """Return the shared webhook log formatter, building it on first use."""
    return WebhookLogFormatter(
        attempts=WEBHOOK_SEND_ATTEMPTS,
        retry_delay_seconds=WEBHOOK_SEND_RETRY_DELAY_SECONDS,
        payload_log_limit=PAYLOAD_LOG_LIMIT,
    )


async def _cancellation_requested() -> bool:
    """Return whether cancellation was requested for the flow run driving this delivery.

    A cancellation that lands while the run waits between attempts is only recorded server-side:
    nothing interrupts the in-process wait, and the next attempt would start anyway and overwrite
    the cancelled state. Each attempt therefore re-checks for a recorded cancellation before
    sending, so the request is honored no matter when it arrived. Outside a flow run there is no
    state to consult and nothing to cancel.
    """
    if flow_run.id is None:
        return False
    async with get_prefect_client(sync_client=False) as client:
        return await PrefectClientAdapter(client).cancellation_requested(flow_run_id=UUID(flow_run.id))


async def _record_http_capture(capture: CapturedHttp) -> None:
    """Record the delivery capture as an artifact on this run.

    Best-effort telemetry: a write failure is logged and swallowed, never raised, so it cannot turn a
    successful delivery into a failure or mask a classified one.
    """
    if flow_run.id is None:
        return
    try:
        async with get_prefect_client(sync_client=False) as client:
            await PrefectClientAdapter(client).create_artifact(
                key=WEBHOOK_HTTP_ARTIFACT_KEY,
                artifact_type=WEBHOOK_HTTP_ARTIFACT_TYPE,
                data=capture.to_artifact_data(),
                flow_run_id=UUID(flow_run.id),
            )
    except Exception as exc:
        get_run_logger().warning(f"Could not record the delivery capture: {exc}")


async def webhook_post(
    webhook_id: str, webhook_kind: str, webhook_name: str, payload: Any, attempt: int | None
) -> Response:
    """Resolve the webhook config, log the outgoing request, and POST the prepared payload.

    Runs inline within the send flow rather than as its own task, so a failed delivery does not add a
    second, redundant failure record to the run logs. An expected delivery failure is classified and
    raised as a delivery error whose traceback is dropped from the run logs, so the failure surfaces
    as a clean classified reason rather than a raw transport stacktrace. An unexpected error
    propagates unchanged and surfaces as a genuine crash.

    Raises:
        WebhookDeliveryError: When an expected delivery failure occurs, carrying the classified reason.

    """
    http_service = get_http()
    log = get_run_logger()
    url = ""
    redacted_headers: dict[str, Any] = {}
    latency_ms: float | None = None
    try:
        webhook = await _resolve_webhook(webhook_id=webhook_id, webhook_kind=webhook_kind)
        url = webhook.url
        headers = webhook.build_headers(payload=payload)
        redacted_headers = webhook.redact_headers(headers)
        log.info(
            get_webhook_log_formatter().outgoing_request(
                webhook_name=webhook_name,
                url=url,
                headers=redacted_headers,
                payload=payload,
                attempt=attempt,
            )
        )
        log.debug(get_webhook_log_formatter().full_payload(webhook_name=webhook_name, payload=payload, attempt=attempt))
        started = time.monotonic()
        response = await webhook.send_payload(payload=payload, http_service=http_service, headers=headers)
        latency_ms = (time.monotonic() - started) * 1_000
        response.raise_for_status()
    except EXPECTED_DELIVERY_ERRORS as cause:
        failure = WebhookFailureClassifier().classify(cause=cause)
        failed_response = cause.response if isinstance(cause, httpx.HTTPStatusError) else None
        await _record_http_capture(
            build_http_capture(
                url=url,
                redacted_headers=redacted_headers,
                status_code=failed_response.status_code if failed_response is not None else None,
                body=failed_response.text if failed_response is not None else None,
                latency_ms=latency_ms,
                failure=failure,
            )
        )
        raise WebhookDeliveryError(failure) from None
    await _record_http_capture(
        build_http_capture(
            url=url,
            redacted_headers=redacted_headers,
            status_code=response.status_code,
            body=response.text,
            latency_ms=latency_ms,
        )
    )
    return response


@flow(
    name="webhook-send",
    flow_run_name="Send webhook {webhook_name}",
    retries=WEBHOOK_SEND_RETRIES,
    retry_delay_seconds=WEBHOOK_SEND_RETRY_DELAY_SECONDS,
)
async def webhook_send(
    webhook_id: str, webhook_kind: str, webhook_name: str, payload: Any, branch_name: str | None = None
) -> Response | State:
    """Send the webhook delivery, retrying the whole send on failure.

    This is the operator-facing delivery: it carries the webhook node and branch tags so it is
    listed and addressable on its own. Expected delivery failures (transport, HTTP status,
    configuration) are classified and re-raised with a clean, user-facing message. An unexpected
    error keeps its traceback so the run surfaces as a genuine crash. A delivery whose
    cancellation was requested ends as cancelled before sending, so no attempt goes out after an
    operator cancelled it.

    Raises:
        WebhookDeliveryError: When an expected delivery failure occurs, carrying the classified reason.

    """
    log = get_run_logger()
    if await _cancellation_requested():
        log.info("Delivery cancellation was requested; ending the run without sending.")
        return Cancelled(message="The delivery was cancelled.")
    await add_tags(nodes=[webhook_id], branches=[branch_name] if branch_name else None)
    # flow_run.run_count is the 1-based attempt number within a flow run; it is None outside one, where
    # there is no retry sequence to report.
    attempt = flow_run.run_count
    started = time.monotonic()
    try:
        response = await webhook_post(
            webhook_id=webhook_id,
            webhook_kind=webhook_kind,
            webhook_name=webhook_name,
            payload=payload,
            attempt=attempt,
        )
    except WebhookDeliveryError as error:
        elapsed_ms = (time.monotonic() - started) * 1_000
        failure = error.failure
        log.error(
            get_webhook_log_formatter().delivery_failed(
                status_class=failure.status_class,
                message=failure.message,
                remediation=failure.remediation,
                attempt=attempt,
                elapsed_ms=elapsed_ms,
            )
        )
        raise
    elapsed_ms = (time.monotonic() - started) * 1_000
    log.info(
        get_webhook_log_formatter().delivery_succeeded(
            url=str(response.url), status_code=response.status_code, attempt=attempt, elapsed_ms=elapsed_ms
        )
    )
    return response


KIND_MAP: dict[str, HeaderKind] = {
    InfrahubKind.STATICKEYVALUE: HeaderKind.STATIC,
    InfrahubKind.ENVKEYVALUE: HeaderKind.ENVIRONMENT,
}


def _extract_custom_headers(webhook_node: CoreWebhook) -> list[WebhookHeader]:
    """Extract WebhookHeader list from a webhook node's headers relationship."""
    if not hasattr(webhook_node, "headers"):
        return []
    headers: list[WebhookHeader] = []
    for related in webhook_node.headers.peers:
        peer = related.peer
        kind = KIND_MAP.get(peer.get_kind())
        if kind is None:
            continue
        headers.append(WebhookHeader(key=peer.key.value, value=peer.value.value, kind=kind))
    return headers


@task(name="webhook-convert-node", task_run_name="Convert node to webhook", cache_policy=NONE)
async def convert_node_to_webhook(webhook_node: CoreWebhook, client: InfrahubClient) -> Webhook:
    webhook_kind = webhook_node.get_kind()
    custom_headers = _extract_custom_headers(webhook_node)

    if webhook_kind == InfrahubKind.STANDARDWEBHOOK:
        return StandardWebhook.from_object(obj=webhook_node, custom_headers=custom_headers)

    # Processing Custom Webhook
    if webhook_node.transformation.id:
        transform = await client.get(
            kind=CoreTransformPython,
            id=webhook_node.transformation.id,
            prefetch_relationships=True,
            include=["name", "class_name", "file_path", "repository"],
        )
        return TransformWebhook.from_object(obj=webhook_node, transform=transform, custom_headers=custom_headers)

    return CustomWebhook.from_object(obj=webhook_node, custom_headers=custom_headers)


def _request_context_from_event(event_payload: dict[str, Any]) -> RequestContext | None:
    """Derive the SDK request context (account and priority) from a raw event payload."""
    infrahub_context = event_payload.get("context")
    if not infrahub_context:
        return None
    return InfrahubEventContext.model_validate(infrahub_context).to_request_context()


async def _resolve_webhook(
    webhook_id: str, webhook_kind: str, request_context: RequestContext | None = None
) -> Webhook:
    """Return the webhook config from cache, or fetch it from the database and cache it.

    Raises:
        ValueError: When the cached webhook type is not a supported webhook kind.

    """
    log = get_run_logger()
    client = get_client()
    if request_context is not None:
        client.request_context = request_context
    cache = await get_cache()

    webhook_data_str = await cache.get(key=f"{CACHE_KEY_PREFIX}:{webhook_id}")
    if not webhook_data_str:
        log.info(f"Webhook {webhook_id} not found in cache")
        webhook_node = await client.get(kind=webhook_kind, id=webhook_id, prefetch_relationships=True)
        webhook = await convert_node_to_webhook(webhook_node=webhook_node, client=client)
        await cache.set(
            key=f"{CACHE_KEY_PREFIX}:{webhook_id}", value=ujson.dumps(webhook.to_cache()), expires=KVTTL.TWO_HOURS
        )
        return webhook

    webhook_data = ujson.loads(webhook_data_str)
    if webhook_data["webhook_type"] not in WEBHOOK_MAP:
        raise ValueError(f"Unsupported webhook kind: {webhook_data['webhook_type']}")
    return WEBHOOK_MAP[webhook_data["webhook_type"]].from_cache(webhook_data)


@flow(name="webhook-process", flow_run_name="Send webhook for {webhook_name}")
async def webhook_process(
    webhook_id: str,
    webhook_name: str,
    webhook_kind: str,
    event_id: str,
    event_type: str,
    event_occured_at: str,
    event_payload: dict,
    branch_name: str | None = None,
) -> State | None:
    """Resolve the webhook config, compute the payload, send it, and surface a clean outcome.

    A classified delivery failure ends the run in a failed state carrying the failure reason and its
    remediation, without a stacktrace, so the run reads as an operational outcome rather than a crash.
    An unexpected error keeps its traceback so it surfaces as a genuine crash.
    """
    client = get_client()
    request_context = _request_context_from_event(event_payload)
    if request_context is not None:
        client.request_context = request_context

    webhook = await _resolve_webhook(webhook_id=webhook_id, webhook_kind=webhook_kind, request_context=request_context)
    webhook_context = EventContext.from_event(
        event_id=event_id,
        event_type=event_type,
        event_occured_at=event_occured_at,
        event_payload=event_payload,
    )
    event_data = event_payload.get("data", {})
    payload = await webhook.compute_payload(data=event_data, context=webhook_context, client=client)
    state = await webhook_send(
        webhook_id=webhook_id,
        webhook_kind=webhook_kind,
        webhook_name=webhook_name,
        payload=payload,
        branch_name=branch_name,
        return_state=True,
    )
    if state.is_completed():
        return None

    # A cancelled delivery carries no result to read; the cancelled state itself is the outcome.
    if state.is_cancelled():
        return state

    # Any other non-completed terminal state (failed, crashed) is surfaced, not reported as success.
    outcome = await state.aresult(raise_on_failure=False)
    if isinstance(outcome, WebhookDeliveryError):
        return Failed(message=f"{outcome.failure.message.rstrip('.')}. {outcome.failure.remediation}")
    if isinstance(outcome, BaseException):
        raise outcome
    return state
