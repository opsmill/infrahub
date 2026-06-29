from __future__ import annotations

import asyncio
from datetime import UTC
from typing import TYPE_CHECKING
from uuid import uuid4

from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterId
from prefect.events.schemas.events import Event, Resource
from prefect.types import DateTime

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.webhook.tasks import configure_webhook
from infrahub.workflows.catalogue import WEBHOOK_PROCESS
from tests.helpers.constants import PREFECT_EVENT_WAIT_SECONDS
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from prefect.client.orchestration import PrefectClient

    from infrahub.database import InfrahubDatabase


class TestWebhookRender(TestInfrahubApp):
    async def test_branchless_event_triggers_webhook_process(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        prefect_client: PrefectClient,
        webhook_deployment: None,
        initial_dataset: None,
    ) -> None:
        """A firing automation renders its parameters on the live Prefect server and runs the deployment.

        A custom webhook listening on every event receives events whose resource carries no branch
        (e.g. account events). The webhook action parameters must render to strings server-side so
        that Prefect dispatches the webhook-process deployment, rather than failing to serialize the
        event id, occurred time, or absent branch.
        """
        webhook = await Node.init(schema=InfrahubKind.CUSTOMWEBHOOK, db=db)
        await webhook.new(
            db=db,
            name="RenderWebhook",
            url="https://url.mock",
            validate_certificates=False,
            event_type="all",
            branch_scope="all_branches",
        )
        await webhook.save(db=db)

        # Create the automation on the live Prefect server.
        await configure_webhook()
        automation_name = f"webhook::{webhook.id}"
        automations = []
        for _ in range(PREFECT_EVENT_WAIT_SECONDS):
            automations = await prefect_client.read_automations_by_name(name=automation_name)
            if automations:
                break
            await asyncio.sleep(1)
        assert automations, f"automation {automation_name} was not configured"

        deployment = await prefect_client.read_deployment_by_name(f"{WEBHOOK_PROCESS.name}/{WEBHOOK_PROCESS.name}")
        deployment_filter = DeploymentFilter(id=DeploymentFilterId(any_=[deployment.id]))
        runs_before = len(await prefect_client.read_flow_runs(deployment_filter=deployment_filter))

        # A branch-less event: the resource carries no infrahub.branch.name, the id is a UUID and the
        # occurred time a datetime -- all values the action parameters must render as plain strings.
        event = Event(
            id=uuid4(),
            event="infrahub.node.created",
            occurred=DateTime(2026, 1, 1, tzinfo=UTC),
            payload={"data": {"node_id": "abc"}, "context": {}},
            resource=Resource({"prefect.resource.id": "infrahub.account.xyz"}),
        )
        await prefect_client._client.post("/events", json=[event.model_dump(mode="json")])

        runs_after = runs_before
        for _ in range(PREFECT_EVENT_WAIT_SECONDS):
            runs_after = len(await prefect_client.read_flow_runs(deployment_filter=deployment_filter))
            if runs_after > runs_before:
                break
            await asyncio.sleep(1)
        assert runs_after > runs_before, "webhook-process deployment was not run; server-side parameter render failed"
