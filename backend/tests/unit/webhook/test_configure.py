from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from prefect.events.schemas.automations import Automation, Posture, ResourceSpecification
from prefect.events.schemas.automations import EventTrigger as PrefectEventTrigger

from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.models import EventTrigger, ExecuteWorkflow, TriggerSetupReport, TriggerType
from infrahub.webhook.models import WebhookTriggerDefinition
from infrahub.webhook.tasks.configure import get_webhooks_to_invalidate
from infrahub.workflows.models import WorkflowDefinition


def _make_webhook_trigger(webhook_id: str) -> WebhookTriggerDefinition:
    return WebhookTriggerDefinition(
        id=webhook_id,
        name="test-webhook",
        trigger=EventTrigger(),
        actions=[
            ExecuteWorkflow(
                workflow=WorkflowDefinition(name="webhook-process", module="m", function="f"),
            )
        ],
    )


def _make_deleted_automation(name: str) -> Automation:
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


async def test_empty_report_returns_empty_set() -> None:
    report = TriggerSetupReport()
    result = await get_webhooks_to_invalidate(report)
    assert result == set()


async def test_collects_ids_from_updated_triggers() -> None:
    report = TriggerSetupReport(
        updated=[_make_webhook_trigger("wh-updated-1"), _make_webhook_trigger("wh-updated-2")],
    )
    result = await get_webhooks_to_invalidate(report)
    assert result == {"wh-updated-1", "wh-updated-2"}


async def test_collects_ids_from_refreshed_triggers() -> None:
    report = TriggerSetupReport(
        refreshed=[_make_webhook_trigger("wh-refreshed-1")],
    )
    result = await get_webhooks_to_invalidate(report)
    assert result == {"wh-refreshed-1"}


async def test_collects_ids_from_deleted_automations() -> None:
    report = TriggerSetupReport(
        deleted=[
            _make_deleted_automation(f"{TriggerType.WEBHOOK.value}{NAME_SEPARATOR}wh-deleted-1"),
            _make_deleted_automation(f"{TriggerType.WEBHOOK.value}{NAME_SEPARATOR}wh-deleted-2"),
        ],
    )
    result = await get_webhooks_to_invalidate(report)
    assert result == {"wh-deleted-1", "wh-deleted-2"}


async def test_combines_updated_refreshed_and_deleted() -> None:
    report = TriggerSetupReport(
        updated=[_make_webhook_trigger("wh-upd")],
        refreshed=[_make_webhook_trigger("wh-ref")],
        deleted=[_make_deleted_automation(f"webhook{NAME_SEPARATOR}wh-del")],
    )
    result = await get_webhooks_to_invalidate(report)
    assert result == {"wh-upd", "wh-ref", "wh-del"}


async def test_ignores_created_and_unchanged_triggers() -> None:
    report = TriggerSetupReport(
        created=[_make_webhook_trigger("wh-created")],
        unchanged=[_make_webhook_trigger("wh-unchanged")],
    )
    result = await get_webhooks_to_invalidate(report)
    assert result == set()
