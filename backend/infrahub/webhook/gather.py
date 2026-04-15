from __future__ import annotations

from prefect import task
from prefect.cache_policies import NONE

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreWebhook
from infrahub.database import InfrahubDatabase  # noqa: TC001  needed for prefect flow

from .models import WebhookTriggerDefinition, WebhookTriggerDefinitionBuilder


@task(name="gather-trigger-webhook", task_run_name="Gather webhook triggers", cache_policy=NONE)
async def gather_trigger_webhook(db: InfrahubDatabase) -> list[WebhookTriggerDefinition]:
    webhooks = await NodeManager.query(db=db, schema=CoreWebhook)
    builder = WebhookTriggerDefinitionBuilder(registry.default_branch)
    return [builder.build(webhook) for webhook in webhooks if webhook.active.value]
