from __future__ import annotations

from infrahub.trigger.models import ExecuteWorkflow
from infrahub.webhook.models import WebhookTriggerData, generate_webhook_automation_name


def _make_data(**overrides: object) -> WebhookTriggerData:
    defaults: dict = {
        "id": "wh-1",
        "name": "my-webhook",
        "event_type": "all",
        "branch_scope": "all",
        "node_kind": None,
        "webhook_kind": "CoreStandardWebhook",
        "active": True,
    }
    defaults.update(overrides)
    return WebhookTriggerData(**defaults)


class TestWebhookTriggerDataToTrigger:
    def test_event_type_all(self) -> None:
        trigger = _make_data(event_type="all").to_trigger(default_branch="main")
        assert trigger.trigger.events == {"infrahub.*"}

    def test_event_type_specific(self) -> None:
        trigger = _make_data(event_type="infrahub.node.created").to_trigger(default_branch="main")
        assert trigger.trigger.events == {"infrahub.node.created"}

    def test_branch_scope_default(self) -> None:
        trigger = _make_data(branch_scope="default_branch").to_trigger(default_branch="main")
        assert trigger.trigger.match_related == {
            "prefect.resource.role": "infrahub.branch",
            "infrahub.resource.label": "main",
        }

    def test_branch_scope_other(self) -> None:
        trigger = _make_data(branch_scope="other_branches").to_trigger(default_branch="main")
        assert trigger.trigger.match_related == {
            "prefect.resource.role": "infrahub.branch",
            "infrahub.resource.label": "!main",
        }

    def test_branch_scope_all(self) -> None:
        trigger = _make_data(branch_scope="all").to_trigger(default_branch="main")
        assert trigger.trigger.match_related == {}

    def test_node_kind_match_with_node_event(self) -> None:
        trigger = _make_data(event_type="infrahub.node.created", node_kind="BuiltinTag").to_trigger(
            default_branch="main"
        )
        assert trigger.trigger.match == {"infrahub.node.kind": "BuiltinTag"}

    def test_node_kind_with_all_event(self) -> None:
        """'all' is treated as a node-kind event, so node_kind filter applies."""
        trigger = _make_data(event_type="all", node_kind="BuiltinTag").to_trigger(default_branch="main")
        assert trigger.trigger.match == {"infrahub.node.kind": "BuiltinTag"}

    def test_node_kind_none(self) -> None:
        trigger = _make_data(event_type="infrahub.node.created", node_kind=None).to_trigger(default_branch="main")
        assert trigger.trigger.match == {}

    def test_workflow_parameters(self) -> None:
        trigger = _make_data(id="wh-42", name="test-hook", webhook_kind="CoreCustomWebhook").to_trigger(
            default_branch="main"
        )
        action = trigger.actions[0]
        assert isinstance(action, ExecuteWorkflow)
        assert action.parameters["webhook_id"] == "wh-42"
        assert action.parameters["webhook_name"] == "test-hook"
        assert action.parameters["webhook_kind"] == "CoreCustomWebhook"

    def test_trigger_id_and_name(self) -> None:
        trigger = _make_data(id="wh-42", name="test-hook").to_trigger(default_branch="main")
        assert trigger.id == "wh-42"
        assert trigger.name == "test-hook"

    def test_generate_name(self) -> None:
        trigger = _make_data(id="wh-42").to_trigger(default_branch="main")
        assert trigger.generate_name() == "webhook::wh-42"


class TestGenerateWebhookAutomationName:
    def test_format(self) -> None:
        assert generate_webhook_automation_name("wh-123") == "webhook::wh-123"
