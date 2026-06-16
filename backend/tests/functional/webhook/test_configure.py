from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import NodeNotFoundError
from infrahub_sdk.protocols import CoreStandardWebhook
from prefect.events.actions import RunDeployment

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreWebhook as CoreWebhookNode
from infrahub.trigger.models import ExecuteWorkflow, TriggerType
from infrahub.trigger.setup import gather_all_automations
from infrahub.webhook.constants import CACHE_KEY_PREFIX
from infrahub.webhook.gather import gather_trigger_webhook
from infrahub.webhook.models import WebhookTriggerDefinition
from infrahub.webhook.tasks import configure_webhook
from infrahub.workflows.catalogue import WEBHOOK_PROCESS
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from prefect.client.orchestration import PrefectClient
    from prefect.events.actions import RunDeployment

    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache


class TestWebhookConfigure(TestInfrahubApp):
    async def test_configure_one(
        self, db: InfrahubDatabase, prefect_client: PrefectClient, webhook1: Node, webhook_deployment: None
    ) -> None:
        await configure_webhook(
            event_type="infrahub.node.created",
            event_data={"node_id": webhook1.id, "changelog": {"display_label": "Webhook1"}},
        )

        name = f"webhook::{webhook1.id}"
        automations = await prefect_client.read_automations_by_name(name=name)
        assert len(automations) == 1
        automation = automations[0]
        assert len(automation.actions) == 1
        action: RunDeployment = automation.actions[0]  # type: ignore[assignment]
        assert action.parameters
        assert "webhook_id" in action.parameters.keys()
        assert action.parameters["webhook_id"] == webhook1.id
        assert "webhook_kind" in action.parameters.keys()
        assert action.parameters["webhook_kind"] == InfrahubKind.STANDARDWEBHOOK

        # Configure it a second time to ensure the function is idempotent
        await configure_webhook(
            event_type="infrahub.node.created",
            event_data={"node_id": webhook1.id, "changelog": {"display_label": "Webhook1"}},
        )
        automations = await prefect_client.read_automations_by_name(name=name)
        assert len(automations) == 1

        # Delete the webhook automation
        await configure_webhook(
            event_type="infrahub.node.deleted",
            event_data={"node_id": webhook1.id, "changelog": {"display_label": "Webhook1"}},
        )
        automations = await prefect_client.read_automations_by_name(name=name)
        assert len(automations) == 0

    async def test_configure_one_inactive_webhook_does_not_create_automation(
        self, db: InfrahubDatabase, prefect_client: PrefectClient, inactive_webhook: Node, webhook_deployment: None
    ) -> None:
        """Test that configuring an inactive webhook does not create a Prefect automation."""
        await configure_webhook(
            event_type="infrahub.node.created",
            event_data={"node_id": inactive_webhook.id, "changelog": {"display_label": "InactiveWebhook"}},
        )

        name = f"webhook::{inactive_webhook.id}"
        automations = await prefect_client.read_automations_by_name(name=name)
        assert len(automations) == 0

    async def test_configure_one_deactivating_webhook_deletes_automation(
        self, db: InfrahubDatabase, prefect_client: PrefectClient, webhook1: Node, webhook_deployment: None
    ) -> None:
        """Test that deactivating a webhook deletes its Prefect automation."""
        # First, ensure the webhook automation exists
        await configure_webhook(
            event_type="infrahub.node.created",
            event_data={"node_id": webhook1.id, "changelog": {"display_label": "Webhook1"}},
        )
        name = f"webhook::{webhook1.id}"
        automations = await prefect_client.read_automations_by_name(name=name)
        assert len(automations) == 1

        # Deactivate the webhook
        webhook1.active.value = False
        await webhook1.save(db=db)

        # Configure again - should delete the automation
        await configure_webhook(
            event_type="infrahub.node.created",
            event_data={"node_id": webhook1.id, "changelog": {"display_label": "Webhook1"}},
        )
        automations = await prefect_client.read_automations_by_name(name=name)
        assert len(automations) == 0

        # Re-activate the webhook for other tests
        webhook1.active.value = True
        await webhook1.save(db=db)

    async def test_gather_trigger_webhook_excludes_inactive(
        self, db: InfrahubDatabase, webhook1: Node, inactive_webhook: Node
    ) -> None:
        """Test that gather_trigger_webhook excludes inactive webhooks."""
        triggers = await gather_trigger_webhook(db=db)
        trigger_ids = [t.id for t in triggers]

        # Active webhook should be included
        assert webhook1.id in trigger_ids
        # Inactive webhook should be excluded
        assert inactive_webhook.id not in trigger_ids

    async def test_configure_all(
        self,
        db: InfrahubDatabase,
        prefect_client: PrefectClient,
        webhook1: Node,
        webhook2: Node,
        webhook_deployment: None,
    ) -> None:
        await configure_webhook()

        automations = await gather_all_automations(client=prefect_client)
        automations_by_name = {automation.name: automation for automation in automations}

        assert f"webhook::{webhook1.id}" in automations_by_name.keys()
        assert f"webhook::{webhook2.id}" in automations_by_name.keys()

        automation = automations_by_name[f"webhook::{webhook2.id}"]
        assert len(automation.actions) == 1
        action: RunDeployment = automation.actions[0]  # type: ignore[assignment]
        assert action.parameters
        assert "webhook_id" in action.parameters.keys()
        assert action.parameters["webhook_id"] == webhook2.id
        assert "webhook_kind" in action.parameters.keys()
        assert action.parameters["webhook_kind"] == InfrahubKind.CUSTOMWEBHOOK

    async def test_configure_all_invalidates_cache(
        self,
        db: InfrahubDatabase,
        memory_cache: MemoryCache,
        webhook1: Node,
        webhook2: Node,
        webhook_deployment: None,
    ) -> None:
        """Test that reconcile_all invalidates caches for updated webhooks."""
        # Modify webhook so reconcile detects it as needing an update
        original_name = webhook1.name.value
        webhook1.name.value = "Webhook1-modified"
        await webhook1.save(db=db)

        await memory_cache.set(key=f"{CACHE_KEY_PREFIX}:{webhook1.id}", value='{"cached": true}')

        await configure_webhook()

        assert await memory_cache.get(key=f"{CACHE_KEY_PREFIX}:{webhook1.id}") is None

        # Restore original name
        webhook1.name.value = original_name
        await webhook1.save(db=db)

    async def test_configure_webhook_on_failure_logs_error(
        self, webhook_deployment: None, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that the on_failure hook logs structured error when configuration fails."""
        with pytest.raises(NodeNotFoundError), caplog.at_level("ERROR"):
            await configure_webhook(
                event_type="infrahub.node.created",
                event_data={"node_id": "non-existent-id", "changelog": {"display_label": "Ghost"}},
            )
        assert "Webhook configuration failed" in caplog.text
        assert "non-existent-id" in caplog.text
        assert "Ghost" in caplog.text
        assert "configure" in caplog.text

    async def test_trigger_definition_node_kind_match(
        self,
        db: InfrahubDatabase,
        webhook4: Node,
        client: InfrahubClient,
    ) -> None:
        webhook = await client.get(kind=CoreStandardWebhook, id=webhook4.id)
        trigger_definition = WebhookTriggerDefinition.from_object(obj=webhook)

        assert trigger_definition.id == webhook4.id
        assert trigger_definition.name == "Webhook4"
        assert trigger_definition.type == TriggerType.WEBHOOK
        assert trigger_definition.trigger.events == {"infrahub.node.created"}
        assert trigger_definition.trigger.match == {"infrahub.node.kind": "BuiltinTag"}
        assert trigger_definition.trigger.match_related == {}
        assert len(trigger_definition.actions) == 1
        action = trigger_definition.actions[0]
        assert isinstance(action, ExecuteWorkflow)
        assert action.workflow == WEBHOOK_PROCESS
        assert action.parameters["webhook_id"] == webhook4.id
        assert action.parameters["webhook_name"] == "Webhook4"
        assert action.parameters["webhook_kind"] == "CoreStandardWebhook"

    async def test_trigger_definition_node_kind_match_via_node_manager(
        self,
        db: InfrahubDatabase,
        webhook4: Node,
    ) -> None:
        webhooks = await NodeManager.query(db=db, schema=CoreWebhookNode)
        webhook = next(w for w in webhooks if w.id == webhook4.id)
        trigger_definition = WebhookTriggerDefinition.from_object(obj=webhook)

        assert trigger_definition.id == webhook4.id
        assert trigger_definition.name == "Webhook4"
        assert trigger_definition.type == TriggerType.WEBHOOK
        assert trigger_definition.trigger.events == {"infrahub.node.created"}
        assert trigger_definition.trigger.match == {"infrahub.node.kind": "BuiltinTag"}
        assert trigger_definition.trigger.match_related == {}
        assert len(trigger_definition.actions) == 1
        action = trigger_definition.actions[0]
        assert isinstance(action, ExecuteWorkflow)
        assert action.workflow == WEBHOOK_PROCESS
        assert action.parameters["webhook_id"] == webhook4.id
        assert action.parameters["webhook_name"] == "Webhook4"
        assert action.parameters["webhook_kind"] == "CoreStandardWebhook"
