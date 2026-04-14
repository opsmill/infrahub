from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreWebhook
from infrahub.trigger.models import ExecuteWorkflow, TriggerType
from infrahub.webhook.models import WebhookTrigger
from infrahub.workflows.catalogue import WEBHOOK_PROCESS

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class TestWebhookToTrigger:
    async def test_standard_webhook(
        self, db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
    ) -> None:
        default_branch.update_schema_hash()

        node = await Node.init(db=db, branch=default_branch, schema="CoreStandardWebhook")
        await node.new(
            db=db,
            name="tag-hook",
            url="https://example.com/hook",
            shared_key="s3cret",
            event_type="infrahub.node.created",
            node_kind="BuiltinTag",
            branch_scope="default_branch",
        )
        await node.save(db=db)

        webhook = await NodeManager.get_one(id=node.id, db=db, kind=CoreWebhook, raise_on_error=True)
        trigger = WebhookTrigger(webhook, default_branch=default_branch.name).definition()

        assert trigger.id == node.id
        assert trigger.name == "tag-hook"
        assert trigger.type == TriggerType.WEBHOOK
        assert not trigger.description
        assert trigger.previous_names == set()
        assert trigger.generate_name() == f"webhook::{node.id}"

        assert trigger.trigger.events == {"infrahub.node.created"}
        assert trigger.trigger.match == {"infrahub.node.kind": "BuiltinTag"}
        assert trigger.trigger.match_related == {
            "prefect.resource.role": "infrahub.branch",
            "infrahub.resource.label": default_branch.name,
        }

        assert len(trigger.actions) == 1
        action = trigger.actions[0]
        assert isinstance(action, ExecuteWorkflow)
        assert action.workflow == WEBHOOK_PROCESS
        assert action.parameters == {
            "webhook_id": node.id,
            "webhook_name": "tag-hook",
            "webhook_kind": "CoreStandardWebhook",
            "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
            "event_id": "{{ event.id }}",
            "event_type": "{{ event.event }}",
            "event_occured_at": "{{ event.occurred }}",
            "event_payload": {
                "__prefect_kind": "json",
                "value": {"__prefect_kind": "jinja", "template": "{{ event.payload | tojson }}"},
            },
        }

    async def test_custom_webhook_with_event_type_all(
        self, db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
    ) -> None:
        default_branch.update_schema_hash()

        node = await Node.init(db=db, branch=default_branch, schema="CoreCustomWebhook")
        await node.new(
            db=db,
            name="custom-hook",
            url="https://example.com/custom",
            branch_scope="all_branches",
        )
        await node.save(db=db)

        webhook = await NodeManager.get_one(id=node.id, db=db, kind=CoreWebhook, raise_on_error=True)
        trigger = WebhookTrigger(webhook, default_branch=default_branch.name).definition()

        assert trigger.id == node.id
        assert trigger.name == "custom-hook"
        assert trigger.type == TriggerType.WEBHOOK
        assert not trigger.description
        assert trigger.previous_names == set()
        assert trigger.generate_name() == f"webhook::{node.id}"

        assert trigger.trigger.events == {"infrahub.*"}
        assert trigger.trigger.match == {}
        assert trigger.trigger.match_related == {}

        assert len(trigger.actions) == 1
        action = trigger.actions[0]
        assert isinstance(action, ExecuteWorkflow)
        assert action.workflow == WEBHOOK_PROCESS
        assert action.parameters == {
            "webhook_id": node.id,
            "webhook_name": "custom-hook",
            "webhook_kind": "CoreCustomWebhook",
            "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
            "event_id": "{{ event.id }}",
            "event_type": "{{ event.event }}",
            "event_occured_at": "{{ event.occurred }}",
            "event_payload": {
                "__prefect_kind": "json",
                "value": {"__prefect_kind": "jinja", "template": "{{ event.payload | tojson }}"},
            },
        }
