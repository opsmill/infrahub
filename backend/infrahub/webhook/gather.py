from __future__ import annotations

from infrahub_sdk import InfrahubClient  # noqa: TC002  needed for prefect flow
from infrahub_sdk.protocols import CoreWebhook
from prefect import task
from prefect.cache_policies import NONE

from .models import WebhookTriggerDefinition


@task(name="gather-trigger-webhook", task_run_name="Gather webhook triggers", cache_policy=NONE)
async def gather_trigger_webhook(client: InfrahubClient) -> list[WebhookTriggerDefinition]:
    webhooks = await client.all(kind=CoreWebhook)
    triggers = [WebhookTriggerDefinition.from_object(webhook) for webhook in webhooks]
    return triggers
