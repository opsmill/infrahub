from datetime import timedelta
from typing import Any

import ujson
from infrahub_sdk.protocols import CoreCustomWebhook, CoreStandardWebhook, CoreTransformPython
from prefect import flow
from prefect.automations import AutomationCore
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterName
from prefect.events.actions import RunDeployment
from prefect.events.schemas.automations import EventTrigger, Posture
from prefect.events.schemas.events import ResourceSpecification
from prefect.logging import get_run_logger

from infrahub.core.constants import InfrahubKind, MutationAction
from infrahub.exceptions import NodeNotFoundError
from infrahub.services import services
from infrahub.workflows.catalogue import WEBHOOK_CONFIGURE, WEBHOOK_SEND, WEBHOOK_TRIGGER

from .constants import AUTOMATION_NAME, AUTOMATION_NAME_RUN
from .models import CustomWebhook, SendWebhookData, StandardWebhook, TransformWebhook, Webhook


@flow(name="event-send-webhook", flow_run_name="Send Webhook")
async def send_webhook(model: SendWebhookData) -> None:
    service = services.service
    log = get_run_logger()

    webhook_definition = await service.cache.get(key=f"webhook:active:{model.webhook_id}")
    if not webhook_definition:
        log.warning("Webhook not found")
        raise NodeNotFoundError(
            node_type="Webhook", identifier=model.webhook_id, message="The requested Webhook was not found"
        )

    webhook_data = ujson.loads(webhook_definition)
    payload: dict[str, Any] = {"event_type": model.event_type, "data": model.event_data, "service": service}
    webhook_map: dict[str, type[Webhook]] = {
        "standard": StandardWebhook,
        "custom": CustomWebhook,
        "transform": TransformWebhook,
    }
    webhook_class = webhook_map[webhook_data["webhook_type"]]
    payload.update(webhook_data["webhook_configuration"])
    webhook = webhook_class(**payload)
    await webhook.send()

    log.info("Successfully sent webhook")


@flow(name="webhook-trigger-actions", flow_run_name="Trigger configured webhooks")
async def trigger_webhooks(event_type: str, event_data: str) -> None:
    service = services.service
    payload: dict = ujson.loads(event_data)

    webhooks = await service.cache.list_keys(filter_pattern="webhook:active:*")
    for webhook in webhooks:
        webhook_id = webhook.split(":")[-1]
        model = SendWebhookData(webhook_id=webhook_id, event_type=event_type, event_data=payload)
        await service.workflow.submit_workflow(workflow=WEBHOOK_SEND, parameters={"model": model})


@flow(name="webhook-setup-automations", flow_run_name="Configuration webhook automation and populate cache")
async def configure_webhooks() -> None:
    service = services.service
    log = get_run_logger()

    log.debug("Refreshing webhook configuration")
    standard_webhooks = await service.client.all(kind=CoreStandardWebhook)
    custom_webhooks = await service.client.all(kind=CoreCustomWebhook)

    expected_webhooks = []
    for webhook in standard_webhooks:
        webhook_key = f"webhook:active:{webhook.id}"
        expected_webhooks.append(webhook_key)
        standard_payload = {
            "webhook_type": "standard",
            "webhook_configuration": {
                "url": webhook.url.value,
                "shared_key": webhook.shared_key.value,
                "validate_certificates": webhook.validate_certificates.value,
            },
        }
        await service.cache.set(key=webhook_key, value=ujson.dumps(standard_payload))

    for webhook in custom_webhooks:
        webhook_key = f"webhook:active:{webhook.id}"
        expected_webhooks.append(webhook_key)
        payload: dict[str, Any] = {
            "webhook_type": "custom",
            "webhook_configuration": {
                "url": webhook.url.value,
                "validate_certificates": webhook.validate_certificates.value,
            },
        }
        if webhook.transformation.id:
            transform = await service.client.get(
                kind=CoreTransformPython,
                id=webhook.transformation.id,
                prefetch_relationships=True,
                populate_store=True,
                include=["name", "class_name", "file_path", "repository"],
            )
            payload["webhook_type"] = "transform"
            payload["webhook_configuration"]["transform_name"] = transform.name.value
            payload["webhook_configuration"]["transform_class"] = transform.class_name.value
            payload["webhook_configuration"]["transform_file"] = transform.file_path.value
            payload["webhook_configuration"]["repository_id"] = transform.repository.id
            payload["webhook_configuration"]["repository_name"] = transform.repository.peer.name.value

        await service.cache.set(key=webhook_key, value=ujson.dumps(payload))

    cached_webhooks = await service.cache.list_keys(filter_pattern="webhook:active:*")
    for cached_webhook in cached_webhooks:
        if cached_webhook not in expected_webhooks:
            await service.cache.delete(key=cached_webhook)

    has_webhooks = bool(expected_webhooks)

    async with get_client(sync_client=False) as client:
        deployments = {
            item.name: item
            for item in await client.read_deployments(
                deployment_filter=DeploymentFilter(
                    name=DeploymentFilterName(
                        any_=[
                            WEBHOOK_TRIGGER.name,
                        ]
                    )
                )
            )
        }
        if WEBHOOK_TRIGGER.name not in deployments:
            raise ValueError("Unable to find the deployment for WEBHOOK_TRIGGER")

        deployment_id_webhook_trigger = deployments[WEBHOOK_TRIGGER.name].id

        webhook_configure_automation = await client.find_automation(id_or_name=AUTOMATION_NAME_RUN)

        if not has_webhooks:
            if webhook_configure_automation:
                await client.delete_automation(automation_id=webhook_configure_automation.id)
            return

        automation = AutomationCore(
            name=AUTOMATION_NAME_RUN,
            description="Trigger all configured webhooks on mutations",
            enabled=True,
            trigger=EventTrigger(
                posture=Posture.Reactive,
                expect={"infrahub.node.*"},
                within=timedelta(0),
                match=ResourceSpecification(
                    {
                        "infrahub.node.action": MutationAction.available_types(),
                    }
                ),
                threshold=1,
            ),
            actions=[
                RunDeployment(
                    source="selected",
                    deployment_id=deployment_id_webhook_trigger,
                    parameters={
                        "event_type": "{{ event.resource['infrahub.node.kind'] }}.{{ event.resource['infrahub.node.action'] }}",
                        "event_data": "{{ event.payload['data'] | tojson }}",
                    },
                    job_variables={},
                ),
            ],
        )

        if webhook_configure_automation:
            await client.update_automation(automation_id=webhook_configure_automation.id, automation=automation)
            log.info(f"{AUTOMATION_NAME_RUN} Updated")
        else:
            await client.create_automation(automation=automation)
            log.info(f"{AUTOMATION_NAME_RUN} Created")


@flow(name="webhook-setup-configuration-trigger", flow_run_name="Setup automations for webhooks")
async def trigger_webhook_configuration() -> None:
    log = get_run_logger()

    async with get_client(sync_client=False) as client:
        deployments = {
            item.name: item
            for item in await client.read_deployments(
                deployment_filter=DeploymentFilter(
                    name=DeploymentFilterName(
                        any_=[
                            WEBHOOK_CONFIGURE.name,
                        ]
                    )
                )
            )
        }
        if WEBHOOK_CONFIGURE.name not in deployments:
            raise ValueError("Unable to find the deployment for WEBHOOK_CONFIGURE")

        deployment_id_webhook_setup = deployments[WEBHOOK_CONFIGURE.name].id

        webhook_configure_automation = await client.find_automation(id_or_name=AUTOMATION_NAME)

        automation = AutomationCore(
            name=AUTOMATION_NAME,
            description="Trigger actions on schema update event",
            enabled=True,
            trigger=EventTrigger(
                posture=Posture.Reactive,
                expect={"infrahub.node.*"},
                within=timedelta(0),
                match=ResourceSpecification(
                    {
                        "infrahub.node.kind": [InfrahubKind.WEBHOOK, InfrahubKind.STANDARDWEBHOOK],
                    }
                ),
                threshold=1,
            ),
            actions=[
                RunDeployment(
                    source="selected",
                    deployment_id=deployment_id_webhook_setup,
                    parameters={},
                    job_variables={},
                ),
            ],
        )

        if webhook_configure_automation:
            await client.update_automation(automation_id=webhook_configure_automation.id, automation=automation)
            log.info(f"{AUTOMATION_NAME} Updated")
        else:
            await client.create_automation(automation=automation)
            log.info(f"{AUTOMATION_NAME} Created")
