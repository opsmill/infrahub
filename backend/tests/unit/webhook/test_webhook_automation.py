from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import create_autospec
from uuid import uuid4

import httpx
import pytest
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.responses import DeploymentResponse
from prefect.events.schemas.automations import Automation, Posture, ResourceSpecification
from prefect.events.schemas.automations import EventTrigger as PrefectEventTrigger

from infrahub.trigger.models import EventTrigger, ExecuteWorkflow
from infrahub.webhook.models import WebhookAutomation, WebhookTriggerDefinition
from infrahub.workflows.models import WorkflowDefinition


def _make_trigger_definition(webhook_id: str = "wh-1", name: str = "test-hook") -> WebhookTriggerDefinition:
    return WebhookTriggerDefinition(
        id=webhook_id,
        name=name,
        trigger=EventTrigger(),
        actions=[
            ExecuteWorkflow(
                workflow=WorkflowDefinition(name="webhook-process", module="m", function="f"),
            )
        ],
    )


def _make_existing_automation(name: str) -> Automation:
    return Automation(
        id=uuid4(),
        name=name,
        trigger=PrefectEventTrigger(
            expect=set(),
            match=ResourceSpecification({"x": "y"}),
            posture=Posture.Reactive,
            threshold=1,
            within=timedelta(0),
        ),
        actions=[],
    )


def _make_response(data: list) -> httpx.Response:
    request = httpx.Request("POST", "http://localhost/automations/filter")
    return httpx.Response(200, content=json.dumps(data).encode(), request=request)


def _stub_no_automations(client: PrefectClient) -> None:
    client.request.return_value = _make_response([])  # type: ignore[attr-defined]


def _stub_existing_automation(client: PrefectClient, automation: Automation) -> None:
    client.request.return_value = _make_response([automation.model_dump(mode="json")])  # type: ignore[attr-defined]


def _stub_deployment(client: PrefectClient) -> None:
    deployment = DeploymentResponse.model_construct(id=uuid4())
    client.read_deployment_by_name.return_value = deployment  # type: ignore[attr-defined]


@pytest.fixture
def prefect_client() -> PrefectClient:
    client = create_autospec(PrefectClient, spec_set=True, instance=True)
    client.create_automation.return_value = uuid4()
    return client


class TestWebhookAutomationProperties:
    def test_name(self) -> None:
        trigger_def = _make_trigger_definition(webhook_id="wh-42")
        automation = WebhookAutomation(trigger_definition=trigger_def, active=True)
        assert automation.name == "webhook::wh-42"

    def test_webhook_id(self) -> None:
        trigger_def = _make_trigger_definition(webhook_id="wh-42")
        automation = WebhookAutomation(trigger_definition=trigger_def, active=True)
        assert automation.webhook_id == "wh-42"

    def test_active(self) -> None:
        trigger_def = _make_trigger_definition()
        assert WebhookAutomation(trigger_definition=trigger_def, active=True).active is True
        assert WebhookAutomation(trigger_definition=trigger_def, active=False).active is False


class TestWebhookAutomationApply:
    async def test_active_no_existing_creates(self, prefect_client: PrefectClient) -> None:
        trigger_def = _make_trigger_definition()
        automation = WebhookAutomation(trigger_definition=trigger_def, active=True)

        _stub_no_automations(prefect_client)
        _stub_deployment(prefect_client)

        await automation.apply(prefect_client)

        prefect_client.create_automation.assert_called_once()  # type: ignore[attr-defined]
        prefect_client.update_automation.assert_not_called()  # type: ignore[attr-defined]
        prefect_client.delete_automation.assert_not_called()  # type: ignore[attr-defined]

    async def test_active_with_existing_updates(self, prefect_client: PrefectClient) -> None:
        trigger_def = _make_trigger_definition()
        automation = WebhookAutomation(trigger_definition=trigger_def, active=True)

        existing = _make_existing_automation(automation.name)
        _stub_existing_automation(prefect_client, existing)
        _stub_deployment(prefect_client)

        await automation.apply(prefect_client)

        prefect_client.create_automation.assert_not_called()  # type: ignore[attr-defined]
        prefect_client.update_automation.assert_called_once()  # type: ignore[attr-defined]
        prefect_client.delete_automation.assert_not_called()  # type: ignore[attr-defined]

    async def test_inactive_with_existing_deletes(self, prefect_client: PrefectClient) -> None:
        trigger_def = _make_trigger_definition()
        automation = WebhookAutomation(trigger_definition=trigger_def, active=False)

        existing = _make_existing_automation(automation.name)
        _stub_existing_automation(prefect_client, existing)

        await automation.apply(prefect_client)

        prefect_client.create_automation.assert_not_called()  # type: ignore[attr-defined]
        prefect_client.update_automation.assert_not_called()  # type: ignore[attr-defined]
        prefect_client.delete_automation.assert_called_once_with(automation_id=existing.id)  # type: ignore[attr-defined]

    async def test_inactive_no_existing_is_noop(self, prefect_client: PrefectClient) -> None:
        trigger_def = _make_trigger_definition()
        automation = WebhookAutomation(trigger_definition=trigger_def, active=False)

        _stub_no_automations(prefect_client)

        await automation.apply(prefect_client)

        prefect_client.create_automation.assert_not_called()  # type: ignore[attr-defined]
        prefect_client.update_automation.assert_not_called()  # type: ignore[attr-defined]
        prefect_client.delete_automation.assert_not_called()  # type: ignore[attr-defined]
