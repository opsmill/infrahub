from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import ujson
from infrahub_sdk import InfrahubClient  # noqa: TC002  needed for prefect flow
from infrahub_sdk.protocols import CoreTransformPython, CoreWebhook
from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger
from prefect.runtime import flow_run
from prefect.states import Failed

from infrahub.core.constants import InfrahubKind
from infrahub.message_bus.types import KVTTL
from infrahub.workers.dependencies import get_cache, get_client, get_http
from infrahub.workflows.utils import add_tags

from ..classifier import EXPECTED_DELIVERY_ERRORS, WebhookDeliveryError, WebhookFailureClassifier
from ..constants import CACHE_KEY_PREFIX
from ..models import CustomWebhook, EventContext, HeaderKind, StandardWebhook, TransformWebhook, Webhook, WebhookHeader

if TYPE_CHECKING:
    from httpx import Response
    from prefect.client.schemas.objects import State


WEBHOOK_MAP: dict[str, type[Webhook]] = {
    "StandardWebhook": StandardWebhook,
    "CustomWebhook": CustomWebhook,
    "TransformWebhook": TransformWebhook,
}


WEBHOOK_SEND_RETRIES: int = 3
WEBHOOK_SEND_RETRY_DELAY_SECONDS: float = 120  # fixed 2m delay between attempts
WEBHOOK_SEND_ATTEMPTS: int = WEBHOOK_SEND_RETRIES + 1  # the initial try plus its retries
PAYLOAD_LOG_LIMIT: int = 2048  # characters shown inline; the full payload is logged at debug level


def _truncate_for_log(text: str) -> str:
    if len(text) <= PAYLOAD_LOG_LIMIT:
        return text
    remaining = len(text) - PAYLOAD_LOG_LIMIT
    return f"{text[:PAYLOAD_LOG_LIMIT]}… (+{remaining} characters; enable debug logging for the full payload)"


def _attempt_phrase(attempt: int | None) -> str:
    """Position this send within its retry sequence, or note that no flow run is driving retries."""
    if attempt is None:
        return "outside a flow run"
    return f"attempt {attempt}/{WEBHOOK_SEND_ATTEMPTS}"


def _log_outgoing_request(
    *, webhook: Webhook, webhook_name: str, attempt: int | None, headers: dict[str, Any], payload: Any
) -> None:
    """Log the outgoing request: a redacted, truncated summary at info and the full payload at debug."""
    log = get_run_logger()
    payload_json = ujson.dumps(payload)
    log.info(
        f"Webhook '{webhook_name}' {_attempt_phrase(attempt)}: POST {webhook.url} "
        f"with headers {webhook.redact_headers(headers)} and payload {_truncate_for_log(payload_json)}"
    )
    log.debug(f"Webhook '{webhook_name}' {_attempt_phrase(attempt)} full payload: {payload_json}")


@task(name="webhook-post", task_run_name="Send webhook {webhook_name}", cache_policy=NONE)
async def webhook_post(
    webhook_id: str, webhook_kind: str, webhook_name: str, payload: Any, attempt: int | None
) -> Response:
    """Resolve the webhook config, log the outgoing request, and POST the prepared payload.

    An expected delivery failure is classified and raised as a delivery error whose traceback is
    dropped from the run logs, so the task failure the engine records here is not the raw transport
    stacktrace. An unexpected error propagates unchanged and surfaces as a genuine crash.

    Raises:
        WebhookDeliveryError: When an expected delivery failure occurs, carrying the classified reason.

    """
    http_service = get_http()
    try:
        webhook = await _resolve_webhook(webhook_id=webhook_id, webhook_kind=webhook_kind)
        headers = webhook.build_headers(payload=payload)
        _log_outgoing_request(
            webhook=webhook, webhook_name=webhook_name, attempt=attempt, headers=headers, payload=payload
        )
        response = await webhook.send_payload(payload=payload, http_service=http_service, headers=headers)
        response.raise_for_status()
    except EXPECTED_DELIVERY_ERRORS as cause:
        raise WebhookDeliveryError(WebhookFailureClassifier().classify(cause=cause)) from None
    return response


@flow(
    name="webhook-send",
    flow_run_name="Send webhook {webhook_name}",
    retries=WEBHOOK_SEND_RETRIES,
    retry_delay_seconds=WEBHOOK_SEND_RETRY_DELAY_SECONDS,
)
async def webhook_send(
    webhook_id: str, webhook_kind: str, webhook_name: str, payload: Any, branch_name: str | None = None
) -> Response:
    """Send the webhook delivery, retrying the whole send on failure.

    This is the operator-facing delivery: it carries the webhook node and branch tags so it is
    listed and addressable on its own. Expected delivery failures (transport, HTTP status,
    configuration) are classified and re-raised with a clean, user-facing message. An unexpected
    error keeps its traceback so the run surfaces as a genuine crash.

    Raises:
        WebhookDeliveryError: When an expected delivery failure occurs, carrying the classified reason.

    """
    log = get_run_logger()
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
        # A retry is only scheduled when a flow run is driving the sequence and attempts remain.
        retry_note = ""
        if attempt is not None:
            retry_note = (
                f" Retrying in {WEBHOOK_SEND_RETRY_DELAY_SECONDS:.0f}s (attempt {attempt + 1}/{WEBHOOK_SEND_ATTEMPTS})."
                if attempt < WEBHOOK_SEND_ATTEMPTS
                else " No retries remaining."
            )
        log.error(
            f"Webhook delivery failed [{failure.status_class}] {_attempt_phrase(attempt)} "
            f"after {elapsed_ms:.0f} ms: {failure.message.rstrip('.')}. {failure.remediation}{retry_note}"
        )
        raise
    elapsed_ms = (time.monotonic() - started) * 1_000
    log.info(
        f"Webhook delivered to {response.url} {_attempt_phrase(attempt)}, "
        f"HTTP {response.status_code} in {elapsed_ms:.0f} ms"
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


async def _resolve_webhook(webhook_id: str, webhook_kind: str) -> Webhook:
    """Return the webhook config from cache, or fetch it from the database and cache it.

    Raises:
        ValueError: When the cached webhook type is not a supported webhook kind.

    """
    log = get_run_logger()
    client = get_client()
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

    webhook = await _resolve_webhook(webhook_id=webhook_id, webhook_kind=webhook_kind)
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

    # Any non-completed terminal state (failed, crashed, cancelled) is surfaced, not reported as success.
    outcome = await state.aresult(raise_on_failure=False)
    if isinstance(outcome, WebhookDeliveryError):
        return Failed(message=f"{outcome.failure.message.rstrip('.')}. {outcome.failure.remediation}")
    if isinstance(outcome, BaseException):
        raise outcome
    return state
