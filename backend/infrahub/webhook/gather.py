from __future__ import annotations

from prefect import task
from prefect.cache_policies import NONE

from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreWebhook
from infrahub.database import InfrahubDatabase  # noqa: TC001  needed for prefect flow

from .models import WebhookTriggerDefinition


@task(name="gather-trigger-webhook", task_run_name="Gather webhook triggers", cache_policy=NONE)
async def gather_trigger_webhook(db: InfrahubDatabase) -> list[WebhookTriggerDefinition]:
    webhooks = await NodeManager.query(db=db, schema=CoreWebhook)
    triggers = [WebhookTriggerDefinition.from_object(webhook) for webhook in webhooks]
    return triggers
