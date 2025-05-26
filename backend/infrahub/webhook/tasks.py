from __future__ import annotations

from typing import TYPE_CHECKING

import ujson
from infrahub_sdk import InfrahubClient  # noqa: TC002  needed for prefect flow
from infrahub_sdk.protocols import CoreTransformPython, CoreWebhook
from prefect import flow, task
from prefect.automations import AutomationCore
from prefect.cache_policies import NONE
from prefect.client.orchestration import get_client
from prefect.logging import get_run_logger

from infrahub.message_bus.types import KVTTL
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import setup_triggers
from infrahub.workflows.utils import add_tags

from .gather import gather_trigger_webhook
from .models import CustomWebhook, EventContext, StandardWebhook, TransformWebhook, Webhook, WebhookTriggerDefinition

if TYPE_CHECKING:
    from httpx import Response

WEBHOOK_MAP: dict[str, type[Webhook]] = {
    "StandardWebhook": StandardWebhook,
    "CustomWebhook": CustomWebhook,
    "TransformWebhook": TransformWebhook,
}


@task(name="webhook-send", task_run_name="Send Standard Webhook {webhook.name}", cache_policy=NONE, retries=3)
async def webhook_send(
    webhook: Webhook, context: EventContext, event_data: dict, service: InfrahubServices
) -> Response:
    response = await webhook.send(data=event_data, context=context, service=service)
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
    service: InfrahubServices,
    branch_name: str | None = None,
) -> None:
    log = get_run_logger()

    if branch_name:
        await add_tags(branches=[branch_name])

    webhook_data_str = await service.cache.get(key=f"webhook:{webhook_id}")
    if not webhook_data_str:
        log.info(f"Webhook {webhook_id} not found in cache")
        webhook_node = await service.client.get(kind=webhook_kind, id=webhook_id)
        webhook = await convert_node_to_webhook(webhook_node=webhook_node, client=service.client)
        webhook_data = webhook.to_cache()
        await service.cache.set(key=f"webhook:{webhook_id}", value=ujson.dumps(webhook_data), expires=KVTTL.TWO_HOURS)

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
    response = await webhook_send(webhook=webhook, context=webhook_context, event_data=event_data, service=service)
    log.info(f"Successfully sent webhook to {response.url} with status {response.status_code}")


@flow(name="webhook-setup-automation-all", flow_run_name="Configure all webhooks")
async def configure_webhook_all(service: InfrahubServices) -> None:
    log = get_run_logger()

    async with service.database.start_session(read_only=True) as db:
        triggers = await gather_trigger_webhook(db=db)

    async with get_client(sync_client=False) as prefect_client:
        await setup_triggers(
            client=prefect_client,
            triggers=triggers,
            trigger_type=TriggerType.WEBHOOK,
        )  # type: ignore[misc]

    log.info(f"{len(triggers)} Webhooks automation configuration completed")


@flow(name="webhook-setup-automation-one", flow_run_name="Configurate webhook for {webhook_name}")
async def configure_webhook_one(
    webhook_name: str,  # noqa: ARG001
    event_data: dict,
    service: InfrahubServices,
) -> None:
    log = get_run_logger()

    webhook = await service.client.get(kind=CoreWebhook, id=event_data["node_id"])
    trigger = WebhookTriggerDefinition.from_object(webhook)

    async with get_client(sync_client=False) as prefect_client:
        # Query the deployment associated with the trigger to have its ID
        deployment_name = trigger.get_deployment_names()[0]
        deployment = await prefect_client.read_deployment_by_name(name=f"{deployment_name}/{deployment_name}")

        automation = AutomationCore(
            name=trigger.generate_name(),
            description=trigger.get_description(),
            enabled=True,
            trigger=trigger.trigger.get_prefect(),
            actions=[action.get(deployment.id) for action in trigger.actions],
        )

        existing_automations = await prefect_client.read_automations_by_name(trigger.generate_name())
        existing_automation = existing_automations[0] if existing_automations else None

        if existing_automation:
            await prefect_client.update_automation(automation_id=existing_automation.id, automation=automation)
            log.info(f"Automation {trigger.generate_name()} updated")
        else:
            await prefect_client.create_automation(automation=automation)
            log.info(f"Automation {trigger.generate_name()} created")

        await service.cache.delete(key=f"webhook:{webhook.id}")


@flow(name="webhook-delete-automation", flow_run_name="Delete webhook automation for {webhook_name}")
async def delete_webhook_automation(
    webhook_id: str,
    webhook_name: str,  # noqa: ARG001
    service: InfrahubServices,
) -> None:
    log = get_run_logger()

    async with get_client(sync_client=False) as prefect_client:
        automation_name = WebhookTriggerDefinition.generate_name_from_id(id=webhook_id)

        existing_automations = await prefect_client.read_automations_by_name(automation_name)
        existing_automation = existing_automations[0] if existing_automations else None

        if existing_automation:
            await prefect_client.delete_automation(automation_id=existing_automation.id)
            log.info(f"Automation {automation_name} deleted")

        await service.cache.delete(key=f"webhook:{webhook_id}")
