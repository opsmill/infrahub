from __future__ import annotations

import copy
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

from prefect.events.schemas.events import Event, Resource
from prefect.server.events.actions import RunDeployment
from prefect.utilities.schema_tools.hydration import HydrationContext, hydrate

from infrahub.core.protocols import CoreWebhook
from infrahub.trigger.models import ExecuteWorkflow
from infrahub.webhook.models import WebhookTriggerDefinitionBuilder, generate_webhook_automation_name


def _make_webhook(**overrides: Any) -> CoreWebhook:
    # event_type.value returns an enum member whose .value is the string
    # all other attributes .value returns the raw value directly
    enum_fields = {"event_type"}
    attr_fields = {"name", "branch_scope", "node_kind", "active"}
    defaults: dict[str, Any] = {
        "id": "wh-1",
        "name": "my-webhook",
        "event_type": "all",
        "branch_scope": "all",
        "node_kind": None,
        "active": True,
    }
    defaults.update(overrides)

    webhook = Mock(spec=CoreWebhook)
    webhook.id = defaults.pop("id")
    webhook.get_kind.return_value = defaults.pop("webhook_kind", "CoreStandardWebhook")
    for key, val in defaults.items():
        if key in enum_fields:
            setattr(webhook, key, Mock(value=Mock(value=val)))
        elif key in attr_fields:
            setattr(webhook, key, Mock(value=val))
    return webhook


class TestWebhookTriggerDefinition:
    def test_event_type_all(self) -> None:
        trigger = WebhookTriggerDefinitionBuilder("main").build(_make_webhook(event_type="all"))
        assert trigger.trigger.events == {"infrahub.*"}

    def test_event_type_specific(self) -> None:
        trigger = WebhookTriggerDefinitionBuilder("main").build(_make_webhook(event_type="infrahub.node.created"))
        assert trigger.trigger.events == {"infrahub.node.created"}

    def test_branch_scope_default(self) -> None:
        trigger = WebhookTriggerDefinitionBuilder("main").build(_make_webhook(branch_scope="default_branch"))
        assert trigger.trigger.match_related == {
            "prefect.resource.role": "infrahub.branch",
            "infrahub.resource.label": "main",
        }

    def test_branch_scope_other(self) -> None:
        trigger = WebhookTriggerDefinitionBuilder("main").build(_make_webhook(branch_scope="other_branches"))
        assert trigger.trigger.match_related == {
            "prefect.resource.role": "infrahub.branch",
            "infrahub.resource.label": "!main",
        }

    def test_branch_scope_all(self) -> None:
        trigger = WebhookTriggerDefinitionBuilder("main").build(_make_webhook(branch_scope="all"))
        assert trigger.trigger.match_related == {}

    def test_node_kind_match_with_node_event(self) -> None:
        trigger = WebhookTriggerDefinitionBuilder("main").build(
            _make_webhook(event_type="infrahub.node.created", node_kind="BuiltinTag")
        )
        assert trigger.trigger.match == {"infrahub.node.kind": "BuiltinTag"}

    def test_node_kind_with_all_event(self) -> None:
        """'all' is treated as a node-kind event, so node_kind filter applies."""
        trigger = WebhookTriggerDefinitionBuilder("main").build(_make_webhook(event_type="all", node_kind="BuiltinTag"))
        assert trigger.trigger.match == {"infrahub.node.kind": "BuiltinTag"}

    def test_node_kind_none(self) -> None:
        trigger = WebhookTriggerDefinitionBuilder("main").build(
            _make_webhook(event_type="infrahub.node.created", node_kind=None)
        )
        assert trigger.trigger.match == {}

    def test_workflow_parameters(self) -> None:
        trigger = WebhookTriggerDefinitionBuilder("main").build(
            _make_webhook(id="wh-42", name="test-hook", webhook_kind="CoreCustomWebhook")
        )
        action = trigger.actions[0]
        assert isinstance(action, ExecuteWorkflow)
        assert action.parameters["webhook_id"] == "wh-42"
        assert action.parameters["webhook_name"] == "test-hook"
        assert action.parameters["webhook_kind"] == "CoreCustomWebhook"

    def test_trigger_id_and_name(self) -> None:
        trigger = WebhookTriggerDefinitionBuilder("main").build(_make_webhook(id="wh-42", name="test-hook"))
        assert trigger.id == "wh-42"
        assert trigger.name == "test-hook"

    def test_generate_name(self) -> None:
        trigger = WebhookTriggerDefinitionBuilder("main").build(_make_webhook(id="wh-42"))
        assert trigger.generate_name() == "webhook::wh-42"


class TestWebhookParameterRender:
    def test_scalar_parameters_render_to_strings(self) -> None:
        """The action parameters render to string values for any triggering event.

        Prefect normalises bare single-expression Jinja parameters before rendering by
        appending a JSON serialisation step. The event id is a UUID, the occurred time is
        a datetime, and an event whose resource carries no branch leaves the branch
        expression undefined -- none JSON-native -- so the parameters must render as plain
        strings rather than relying on those values being JSON-serialisable.
        """
        trigger = WebhookTriggerDefinitionBuilder("main").build(_make_webhook(event_type="all"))
        action = trigger.actions[0]
        assert isinstance(action, ExecuteWorkflow)
        parameters = copy.deepcopy(action.parameters)

        # A branch-less event (e.g. an account event) whose resource has no branch name.
        # `occurred` is left to default to a datetime, which is itself not JSON-native.
        event = Event(
            id=uuid4(),
            event="infrahub.node.created",
            payload={"data": {"id": "abc"}, "context": {}},
            resource=Resource({"prefect.resource.id": "infrahub.account.xyz"}),
        )

        # Mirror Prefect's server-side parameter render that runs when the automation fires.
        RunDeployment._upgrade_v1_templates(parameters)
        rendered = hydrate(
            parameters,
            HydrationContext(raise_on_error=True, render_jinja=True, jinja_context={"event": event}),
        )

        assert rendered["event_id"] == str(event.id)
        assert rendered["event_type"] == "infrahub.node.created"
        assert rendered["event_occured_at"] == str(event.occurred)
        assert isinstance(rendered["branch_name"], str)
        assert not rendered["branch_name"]


class TestGenerateWebhookAutomationName:
    def test_format(self) -> None:
        assert generate_webhook_automation_name("wh-123") == "webhook::wh-123"
