from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import ujson
from infrahub_sdk import InfrahubClient  # noqa: TC002  needed for prefect flow
from infrahub_sdk.protocols import CoreTransformPython, CoreWebhook
from prefect import flow, task
from prefect.automations import AutomationCore
from prefect.cache_policies import NONE
from prefect.client.orchestration import get_client as get_prefect_client
from prefect.logging import get_run_logger
from prefect.runtime import flow_run

from infrahub.message_bus.types import KVTTL
from infrahub.trigger.models import ExecuteWorkflow, TriggerType
from infrahub.trigger.setup import gather_all_automations, setup_triggers_specific
from infrahub.workers.dependencies import get_cache, get_client, get_database, get_http
from infrahub.workflows.utils import add_tags

from .constants import EVENT_TO_ACTION, WebhookAction
from .gather import gather_trigger_webhook
from .models import CustomWebhook, EventContext, StandardWebhook, TransformWebhook, Webhook, WebhookTriggerDefinition

if TYPE_CHECKING:
    from httpx import Response
    from prefect import Flow, State
    from prefect.client.schemas.objects import FlowRun


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


@dataclass
class WebhookConfigureParams:
    action: WebhookAction
    webhook_id: str | None
    webhook_name: str | None

    @property
    def required_webhook_id(self) -> str:
        if not self.webhook_id:
            raise ValueError(f"webhook_id is required for action {self.action}")
        return self.webhook_id

    @property
    def run_name(self) -> str:
        name = f"Configure webhook ({self.action})"
        if self.webhook_name:
            name += f" - {self.webhook_name}"
        return name


def parse_flow_params(event_type: str | None, event_data: dict | None) -> WebhookConfigureParams:
    """Parse raw flow parameters into a structured WebhookConfigureParams.

    Maps event types to actions via EVENT_TO_ACTION. Defaults to RECONCILE_ALL
    when no event_type is provided (e.g. scheduled runs).
    """
    if event_type and event_type not in EVENT_TO_ACTION:
        raise ValueError(f"Unknown webhook event type: {event_type}")

    action = EVENT_TO_ACTION[event_type] if event_type else WebhookAction.RECONCILE_ALL
    webhook_id = event_data["node_id"] if event_data else None
    webhook_name = event_data.get("changelog", {}).get("display_label") if event_data else None
    return WebhookConfigureParams(action=action, webhook_id=webhook_id, webhook_name=webhook_name)


def _configure_webhook_run_name() -> str:
    """Generate a dynamic Prefect flow run name from the current run's parameters."""
    params = flow_run.parameters
    return parse_flow_params(
        event_type=params.get("event_type"),
        event_data=params.get("event_data"),
    ).run_name


async def _configure_webhook_on_failure(flow: Flow, flow_run: FlowRun, state: State) -> None:  # noqa: ARG001
    """Log structured error when webhook configuration fails."""
    run_log = get_run_logger()
    parsed = parse_flow_params(
        event_type=flow_run.parameters.get("event_type"),
        event_data=flow_run.parameters.get("event_data"),
    )
    run_log.error(
        "Webhook configuration failed: action=%s webhook_id=%s webhook_name=%s state_message=%s",
        parsed.action,
        parsed.webhook_id,
        parsed.webhook_name,
        state.message,
    )


@flow(name="webhook-configure", flow_run_name=_configure_webhook_run_name, on_failure=[_configure_webhook_on_failure])
async def configure_webhook(
    event_type: str | None = None,
    event_data: dict | None = None,
) -> None:
    """Entry point for webhook automation configuration.

    Routes to the appropriate handler based on the event type: configure a single
    webhook, delete an automation, or reconcile all webhooks.
    """
    parsed = parse_flow_params(event_type=event_type, event_data=event_data)

    match parsed.action:
        case WebhookAction.CONFIGURE:
            await _configure_one(webhook_id=parsed.required_webhook_id, webhook_name=parsed.webhook_name)
        case WebhookAction.DELETE:
            await _delete_automation(webhook_id=parsed.required_webhook_id)
        case WebhookAction.RECONCILE_ALL:
            await _reconcile_all()


async def _reconcile_all() -> None:
    """Sync all active webhooks with Prefect automations.

    Delegates to setup_triggers_specific which creates missing automations,
    updates existing ones, and removes automations for deleted webhooks.
    """
    log = get_run_logger()

    database = await get_database()
    async with database.start_session(read_only=True) as db:
        triggers = await gather_trigger_webhook(db=db)

    await setup_triggers_specific(gatherer=gather_trigger_webhook, db=database, trigger_type=TriggerType.WEBHOOK)  # type: ignore[arg-type]
    log.info(f"{len(triggers)} Webhooks automation configuration completed")


async def _configure_one(
    webhook_id: str,
    webhook_name: str | None,
) -> None:
    """Create or update a Prefect automation for a single webhook.

    If the webhook is inactive, deletes the existing automation instead.
    Always invalidates the webhook cache to ensure fresh config on next execution.
    """
    log = get_run_logger()

    webhook = await get_client().get(kind=CoreWebhook, id=webhook_id)
    trigger = WebhookTriggerDefinition.from_object(webhook)

    async with get_prefect_client(sync_client=False) as prefect_client:
        all_automations = await gather_all_automations(client=prefect_client)
        existing_automations = [
            automation for automation in all_automations if automation.name == trigger.generate_name()
        ]
        existing_automation = existing_automations[0] if existing_automations else None

        # If webhook is inactive, delete the automation if it exists
        if not webhook.active.value:
            if existing_automation:
                await prefect_client.delete_automation(automation_id=existing_automation.id)
                log.info(f"Automation {trigger.generate_name()} deleted (webhook disabled)")
            else:
                log.info(f"Webhook {webhook_name} is disabled, no automation to delete")

            cache = await get_cache()
            await cache.delete(key=f"webhook:{webhook.id}")
            return

        # Query the deployment associated with the trigger to have its ID
        deployment_name = trigger.get_deployment_names()[0]
        deployment = await prefect_client.read_deployment_by_name(name=f"{deployment_name}/{deployment_name}")

        automation = AutomationCore(
            name=trigger.generate_name(),
            description=trigger.get_description(),
            enabled=True,
            trigger=trigger.trigger.get_prefect(),
            actions=[action.get(deployment.id) for action in trigger.actions if isinstance(action, ExecuteWorkflow)],
        )

        if existing_automation:
            await prefect_client.update_automation(automation_id=existing_automation.id, automation=automation)
            log.info(f"Automation {trigger.generate_name()} updated")
        else:
            await prefect_client.create_automation(automation=automation)
            log.info(f"Automation {trigger.generate_name()} created")

        cache = await get_cache()
        await cache.delete(key=f"webhook:{webhook.id}")


async def _delete_automation(
    webhook_id: str,
) -> None:
    """Delete the Prefect automation for a webhook and invalidate its cache."""
    log = get_run_logger()

    async with get_prefect_client(sync_client=False) as prefect_client:
        automation_name = WebhookTriggerDefinition.generate_name_from_id(id=webhook_id)

        all_automations = await gather_all_automations(client=prefect_client)
        existing_automations = [automation for automation in all_automations if automation.name == automation_name]
        existing_automation = existing_automations[0] if existing_automations else None

        if existing_automation:
            await prefect_client.delete_automation(automation_id=existing_automation.id)
            log.info(f"Automation {automation_name} deleted")

        cache = await get_cache()
        await cache.delete(key=f"webhook:{webhook_id}")
