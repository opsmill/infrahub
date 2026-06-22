from __future__ import annotations

from typing import TYPE_CHECKING, Any

import ujson
from infrahub_sdk import InfrahubClient  # noqa: TC002  needed for prefect flow
from infrahub_sdk.protocols import CoreTransformPython, CoreWebhook
from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

from infrahub.core.constants import InfrahubKind
from infrahub.message_bus.types import KVTTL
from infrahub.workers.dependencies import get_cache, get_client, get_http
from infrahub.workflows.utils import add_tags

from ..constants import CACHE_KEY_PREFIX
from ..models import CustomWebhook, EventContext, HeaderKind, StandardWebhook, TransformWebhook, Webhook, WebhookHeader

if TYPE_CHECKING:
    from httpx import Response


WEBHOOK_MAP: dict[str, type[Webhook]] = {
    "StandardWebhook": StandardWebhook,
    "CustomWebhook": CustomWebhook,
    "TransformWebhook": TransformWebhook,
}


@flow(name="webhook-send", flow_run_name="Send webhook {webhook_name}", retries=3)
async def webhook_send(webhook_id: str, webhook_kind: str, webhook_name: str, payload: Any) -> Response:  # noqa: ARG001
    """Resolve the webhook config, assign its headers, and POST the prepared payload. Retries up to 3 times."""
    log = get_run_logger()
    http_service = get_http()
    webhook = await _resolve_webhook(webhook_id=webhook_id, webhook_kind=webhook_kind)
    response = await webhook.send_payload(payload=payload, http_service=http_service)
    response.raise_for_status()
    log.info(f"Successfully sent webhook to {response.url} with status {response.status_code}")
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
) -> None:
    """Resolve the webhook config, compute the payload once, and hand it to the send flow."""
    client = get_client()

    await add_tags(nodes=[webhook_id], branches=[branch_name] if branch_name else None)

    webhook = await _resolve_webhook(webhook_id=webhook_id, webhook_kind=webhook_kind)
    webhook_context = EventContext.from_event(
        event_id=event_id,
        event_type=event_type,
        event_occured_at=event_occured_at,
        event_payload=event_payload,
    )
    event_data = event_payload.get("data", {})
    payload = await webhook.compute_payload(data=event_data, context=webhook_context, client=client)
    await webhook_send(webhook_id=webhook_id, webhook_kind=webhook_kind, webhook_name=webhook_name, payload=payload)
