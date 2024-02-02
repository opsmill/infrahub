import json
from typing import Dict, Type

from infrahub_sdk.uuidt import UUIDT

from infrahub.message_bus import messages
from infrahub.services import InfrahubServices
from infrahub.webhook import CustomWebhook, StandardWebhook, TransformWebhook, Webhook


async def event(message: messages.SendWebhookEvent, service: InfrahubServices) -> None:
    webhook_definition = await service.cache.get(key=f"webhook:active:{message.webhook_id}")
    if not webhook_definition:
        service.log.warning("Webhook not found", webhook_id=message.webhook_id)
        return
    task_id = str(UUIDT())
    await service.client.execute_graphql(
        query=CREATE_TASK,
        variables={
            "conclusion": "UNKNOWN",
            "related_node": message.webhook_id,
            "task_id": task_id,
            "title": "Webhook",
        },
    )
    webhook_data = json.loads(webhook_definition)
    payload = {"event_type": message.event_type, "data": message.event_data, "service": service}
    webhook_map: Dict[str, Type[Webhook]] = {
        "standard": StandardWebhook,
        "custom": CustomWebhook,
        "transform": TransformWebhook,
    }
    webhook_class = webhook_map[webhook_data["webhook_type"]]
    payload.update(webhook_data["webhook_configuration"])
    webhook = webhook_class(**payload)
    try:
        await webhook.send()
        await service.client.execute_graphql(
            query=UPDATE_TASK,
            variables={
                "conclusion": "SUCCESS",
                "task_id": task_id,
                "title": webhook.webhook_type,
                "logs": {"message": "Successfully sent webhook", "severity": "INFO"},
            },
        )

    except Exception as exc:
        await service.client.execute_graphql(
            query=UPDATE_TASK,
            variables={
                "conclusion": "FAILURE",
                "task_id": task_id,
                "title": webhook.webhook_type,
                "logs": {"message": str(exc), "severity": "ERROR"},
            },
        )
        raise exc


CREATE_TASK = """
mutation CreateTask(
    $conclusion: TaskConclusion!,
    $title: String!,
    $task_id: UUID,
    $related_node: String!
    $logs: [RelatedTaskLogCreateInput]
    ) {
    InfrahubTaskCreate(
        data: {
            id: $task_id,
            title: $title,
            related_node: $related_node,
            conclusion: $conclusion,
            logs: $logs
        }
    ) {
        ok
    }
}
"""

UPDATE_TASK = """
mutation UpdateTask(
    $conclusion: TaskConclusion,
    $title: String,
    $task_id: UUID!,
    $logs: [RelatedTaskLogCreateInput]
    ) {
    InfrahubTaskUpdate(
        data: {
            id: $task_id,
            title: $title,
            conclusion: $conclusion,
            logs: $logs
        }
    ) {
        ok
    }
}
"""
