from __future__ import annotations

from typing import TYPE_CHECKING

import ujson
from infrahub_sdk import InfrahubClient  # noqa: TC002  needed for prefect flow
from infrahub_sdk.protocols import CoreTransformPython, CoreWebhook
from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

from infrahub.message_bus.types import KVTTL
from infrahub.workers.dependencies import get_cache, get_client, get_http
from infrahub.workflows.utils import add_tags

from ..models import CustomWebhook, EventContext, StandardWebhook, TransformWebhook, Webhook

if TYPE_CHECKING:
    from httpx import Response


WEBHOOK_MAP: dict[str, type[Webhook]] = {
    "StandardWebhook": StandardWebhook,
    "CustomWebhook": CustomWebhook,
    "TransformWebhook": TransformWebhook,
}


@task(name="webhook-send", task_run_name="Send Standard Webhook {webhook.name}", cache_policy=NONE, retries=3)
async def webhook_send(webhook: Webhook, context: EventContext, event_data: dict) -> Response:
    """Send an HTTP request to the webhook endpoint. Retries up to 3 times on failure."""
    http_service = get_http()
    client = get_client()
    response = await webhook.send(data=event_data, context=context, http_service=http_service, client=client)
    response.raise_for_status()
    return response


@task(name="webhook-convert-node", task_run_name="Convert node to webhook", cache_policy=NONE)
async def convert_node_to_webhook(webhook_node: CoreWebhook, client: InfrahubClient) -> Webhook:
    webhook_kind = webhook_node.get_kind()

    if webhook_kind not in ["CoreStandardWebhook", "CoreCustomWebhook"]:
        raise ValueError(f"Unsupported webhook kind: {webhook_kind}")

    if webhook_kind == "CoreStandardWebhook":
        return StandardWebhook.from_object(obj=webhook_node)

    # Processing Custom Webhook
    if webhook_node.transformation.id:
        transform = await client.get(
            kind=CoreTransformPython,
            id=webhook_node.transformation.id,
            prefetch_relationships=True,
            include=["name", "class_name", "file_path", "repository"],
        )
        return TransformWebhook.from_object(obj=webhook_node, transform=transform)

    return CustomWebhook.from_object(obj=webhook_node)


@flow(name="webhook-process", flow_run_name="Send webhook for {webhook_name}")
async def webhook_process(
    webhook_id: str,
    webhook_name: str,  # noqa: ARG001
    webhook_kind: str,
    event_id: str,
    event_type: str,
    event_occured_at: str,
    event_payload: dict,
    branch_name: str | None = None,
) -> None:
    """Resolve a webhook's configuration from cache (or DB on miss) and send the HTTP request."""
    log = get_run_logger()
    client = get_client()
    cache = await get_cache()

    if branch_name:
        await add_tags(branches=[branch_name])

    webhook_data_str = await cache.get(key=f"webhook:{webhook_id}")
    if not webhook_data_str:
        log.info(f"Webhook {webhook_id} not found in cache")
        webhook_node = await client.get(kind=webhook_kind, id=webhook_id)
        webhook = await convert_node_to_webhook(webhook_node=webhook_node, client=client)
        webhook_data = webhook.to_cache()
        await cache.set(key=f"webhook:{webhook_id}", value=ujson.dumps(webhook_data), expires=KVTTL.TWO_HOURS)

    else:
        webhook_data = ujson.loads(webhook_data_str)

        if webhook_data["webhook_type"] not in WEBHOOK_MAP:
            raise ValueError(f"Unsupported webhook kind: {webhook_data['webhook_type']}")

        webhook_class = WEBHOOK_MAP[webhook_data["webhook_type"]]
        webhook = webhook_class.from_cache(webhook_data)

    webhook_context = EventContext.from_event(
        event_id=event_id,
        event_type=event_type,
        event_occured_at=event_occured_at,
        event_payload=event_payload,
    )
    event_data = event_payload.get("data", {})
    response = await webhook_send(webhook=webhook, context=webhook_context, event_data=event_data)
    log.info(f"Successfully sent webhook to {response.url} with status {response.status_code}")
