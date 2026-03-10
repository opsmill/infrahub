from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator

import httpx
import pytest
from infrahub_sdk.exceptions import NodeNotFoundError
from infrahub_sdk.protocols import CoreStandardWebhook
from prefect.client.orchestration import PrefectClient, get_client
from prefect.events.actions import RunDeployment

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.trigger.setup import gather_all_automations
from infrahub.webhook.gather import gather_trigger_webhook
from infrahub.webhook.models import EventContext, WebhookTriggerDefinition
from infrahub.webhook.tasks import (
    configure_webhook,
    convert_node_to_webhook,
    webhook_process,
)
from infrahub.workers.dependencies import build_http_service
from infrahub.workflows.catalogue import WEBHOOK_CONFIGURE, WEBHOOK_PROCESS, WORKER_POOLS
from infrahub.workflows.initialization import setup_worker_pools
from tests.adapters.http import MemoryHTTP
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient
    from prefect.events.actions import RunDeployment

    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

BRANCH_CREATED_PAYLOAD: dict[str, Any] = {
    "context": {
        "event": {
            "id": "24790022-2bc8-42ab-a447-bf3e84675901",
            "name": "infrahub.branch.created",
            "ancestors": [],
            "parent_id": None,
        },
        "branch": {"id": "182853ef-58a3-b3cc-3e80-c5161f4171c1", "name": "-global-"},
        "account": {
            "auth_type": "api",
            "account_id": "182853f2-3a43-c7f9-3e84-c5152eff4b17",
            "session_id": None,
            "authenticated": None,
        },
    }
}


class TestWebhookTasks(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        register_core_schema: SchemaBranch,
        client: InfrahubClient,
        git_repos_source_dir_module_scope: Path,
        prefect_test_fixture: None,
    ) -> None:
        await load_schema(db, schema=CAR_SCHEMA)

        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, age=25, description="The famous Joe Doe")
        await john.save(db=db)

        koenigsegg = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await koenigsegg.new(db=db, name="Koenigsegg")
        await koenigsegg.save(db=db)

        people = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await people.new(db=db, name="people", members=[john])
        await people.save(db=db)

        jesko = await Node.init(schema=TestKind.CAR, db=db)
        await jesko.new(
            db=db,
            name="Jesko",
            color="Red",
            description="A limited production mid-engine sports car",
            owner=john,
            manufacturer=koenigsegg,
        )
        await jesko.save(db=db)

        FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
        )
        await client_repository.save()

    @pytest.fixture(scope="class")
    async def prefect_client(self, prefect_test_fixture: None) -> AsyncGenerator[PrefectClient, None]:
        async with get_client(sync_client=False) as client:
            yield client

    @pytest.fixture(scope="class")
    async def webhook_deployment(self, db: InfrahubDatabase, prefect_client: PrefectClient) -> None:
        await setup_worker_pools(client=prefect_client)
        await WEBHOOK_PROCESS.save(client=prefect_client, work_pool=WORKER_POOLS[0])
        await WEBHOOK_CONFIGURE.save(client=prefect_client, work_pool=WORKER_POOLS[0])

    @pytest.fixture(scope="class")
    async def webhook1(self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient) -> Node:
        webhook = await Node.init(schema=InfrahubKind.STANDARDWEBHOOK, db=db)
        await webhook.new(
            db=db,
            name="Webhook1",
            url="https://url.mock",
            shared_key="1234567890",
            validate_certificates=False,
            event_type="infrahub.branch.created",
            branch_scope="all_branches",
        )
        await webhook.save(db=db)
        return webhook

    @pytest.fixture(scope="class")
    async def webhook2(self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient) -> Node:
        transform = await client.get(
            kind=InfrahubKind.TRANSFORMPYTHON, name__value="WebhookTransformer", raise_when_missing=True
        )

        webhook = await Node.init(schema=InfrahubKind.CUSTOMWEBHOOK, db=db)
        await webhook.new(
            db=db,
            name="Webhook2",
            url="https://url.mock",
            validate_certificates=False,
            event_type="infrahub.node.updated",
            branch_scope="all_branches",
            transformation=transform.id,
        )
        await webhook.save(db=db)
        return webhook

    @pytest.fixture(scope="class")
    async def webhook3(self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient) -> Node:
        webhook = await Node.init(schema=InfrahubKind.CUSTOMWEBHOOK, db=db)
        await webhook.new(
            db=db,
            name="Webhook3",
            url="https://url.mock",
            validate_certificates=False,
            event_type="infrahub.node.created",
            branch_scope="other_branches",
        )
        await webhook.save(db=db)
        return webhook

    @pytest.fixture(scope="class")
    async def webhook4(self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient) -> Node:
        webhook = await Node.init(schema=InfrahubKind.STANDARDWEBHOOK, db=db)
        await webhook.new(
            db=db,
            name="Webhook4",
            url="https://url.mock",
            shared_key="1234567890",
            validate_certificates=False,
            node_kind="BuiltinTag",
            event_type="infrahub.node.created",
            branch_scope="all_branches",
        )
        await webhook.save(db=db)
        return webhook

    @pytest.fixture(scope="class")
    async def inactive_webhook(self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient) -> Node:
        webhook = await Node.init(schema=InfrahubKind.STANDARDWEBHOOK, db=db)
        await webhook.new(
            db=db,
            name="InactiveWebhook",
            url="https://url.mock",
            shared_key="1234567890",
            validate_certificates=False,
            event_type="infrahub.node.created",
            branch_scope="all_branches",
            active=False,
        )
        await webhook.save(db=db)
        return webhook

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
        assert action.parameters["webhook_kind"] == "CoreStandardWebhook"

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
        assert action.parameters["webhook_kind"] == "CoreCustomWebhook"

    async def test_convert_node_to_webhook_standard(
        self,
        db: InfrahubDatabase,
        webhook1: Node,
        client: InfrahubClient,
    ) -> None:
        webhook = await client.get(kind=InfrahubKind.STANDARDWEBHOOK, id=webhook1.id)
        converted_webhook = await convert_node_to_webhook(webhook_node=webhook, client=client)

        assert converted_webhook.model_dump() == {
            "name": "Webhook1",
            "url": "https://url.mock",
            "event_type": "infrahub.branch.created",
            "validate_certificates": False,
            "shared_key": "1234567890",
            "webhook_type": "StandardWebhook",
        }

    async def test_convert_node_to_webhook_transform(
        self,
        db: InfrahubDatabase,
        webhook2: Node,
        client: InfrahubClient,
    ) -> None:
        webhook = await client.get(kind=InfrahubKind.CUSTOMWEBHOOK, id=webhook2.id)
        converted_webhook = await convert_node_to_webhook(webhook_node=webhook, client=client)

        assert converted_webhook.model_dump(exclude={"repository_id"}) == {
            "event_type": "infrahub.node.updated",
            "name": "Webhook2",
            "repository_kind": "CoreRepository",
            "repository_name": "car-dealership",
            "convert_query_response": False,
            "shared_key": None,
            "transform_class": "WebhookTransformer",
            "transform_file": "transforms/webhook_transformer.py",
            "transform_name": "WebhookTransformer",
            "transform_timeout": 5,
            "url": "https://url.mock",
            "validate_certificates": False,
            "webhook_type": "TransformWebhook",
        }

    async def test_process_standard_webhook_success(
        self,
        db: InfrahubDatabase,
        prefect_client: PrefectClient,
        webhook1: Node,
        webhook2: Node,
        webhook_deployment: None,
        dependency_provider: Provider,
    ) -> None:
        http = MemoryHTTP()
        http.add_post_response(
            url="https://url.mock",
            response=httpx.Response(request=httpx.Request(method="GET", url="https://url.mock"), status_code=200),
        )
        with dependency_provider.scope(build_http_service, lambda: http):
            await webhook_process(
                webhook_id=webhook1.id,
                webhook_name="Webhook1",
                webhook_kind="CoreStandardWebhook",
                event_id="ce3b7013-4abb-4945-89de-1f56da4ff636",
                event_type="infrahub.branch.created",
                event_occured_at="2025-02-28T08:37:09.969Z",
                event_payload=BRANCH_CREATED_PAYLOAD,
            )

    async def test_process_standard_webhook_failure(
        self,
        db: InfrahubDatabase,
        prefect_client: PrefectClient,
        webhook1: Node,
        webhook2: Node,
        webhook_deployment: None,
        dependency_provider: Provider,
    ) -> None:
        http = MemoryHTTP()
        http.add_post_response(
            url="https://url.mock",
            response=httpx.Response(request=httpx.Request(method="GET", url="https://url.mock"), status_code=404),
        )

        with pytest.raises(httpx.HTTPStatusError), dependency_provider.scope(build_http_service, lambda: http):
            await webhook_process(
                webhook_id=webhook1.id,
                webhook_name="Webhook1",
                webhook_kind="CoreStandardWebhook",
                branch_name="main",
                event_id="ce3b7013-4abb-4945-89de-1f56da4ff636",
                event_type="infrahub.branch.created",
                event_occured_at="2025-02-28T08:37:09.969Z",
                event_payload=BRANCH_CREATED_PAYLOAD,
            )

    async def test_webhook_check_payload_transform(
        self,
        db: InfrahubDatabase,
        webhook2: Node,
        client: InfrahubClient,
    ) -> None:
        node = await client.get(kind=InfrahubKind.CUSTOMWEBHOOK, id=webhook2.id)
        webhook = await convert_node_to_webhook(webhook_node=node, client=client)

        context = EventContext.from_event(
            event_id="ce3b7013-4abb-4945-89de-1f56da4ff636",
            event_type="infrahub.branch.created",
            event_occured_at="2025-02-28T08:37:09.969Z",
            event_payload=BRANCH_CREATED_PAYLOAD,
        )

        await webhook.prepare(data={}, context=context, client=client)

        assert webhook.get_payload() == {
            "ACCOUNT_ID": "182853f2-3a43-c7f9-3e84-c5152eff4b17",
            "BRANCH": None,
            "DATA": {},
            "EVENT": "infrahub.branch.created",
            "ID": "ce3b7013-4abb-4945-89de-1f56da4ff636",
            "OCCURED_AT": "2025-02-28T08:37:09.969Z",
        }

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
        assert trigger_definition.trigger.match == {"infrahub.node.kind": "BuiltinTag"}
