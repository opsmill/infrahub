from typing import List

from prefect import flow

from infrahub.message_bus import InfrahubMessage, messages
from infrahub.send.models import SendWebhookData
from infrahub.services import InfrahubServices
from infrahub.workflows.catalogue import WEBHOOK_SEND


@flow(name="webhook-trigger-actions")
async def actions(message: messages.TriggerWebhookActions, service: InfrahubServices) -> None:
    webhooks = await service.cache.list_keys(filter_pattern="webhook:active:*")
    events: List[InfrahubMessage] = []
    for webhook in webhooks:
        webhook_id = webhook.split(":")[-1]
        model = SendWebhookData(webhook_id=webhook_id, event_type=message.event_type, event_data=message.event_data)
        await service.workflow.submit_workflow(workflow=WEBHOOK_SEND, parameters={"model": model})

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)
