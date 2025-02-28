from __future__ import annotations

from typing import TYPE_CHECKING, AsyncGenerator

import pytest
from prefect.client.orchestration import PrefectClient, get_client
from prefect.events.actions import RunDeployment
from tests.helpers.test_app import TestInfrahubApp

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.webhook.tasks import configure_webhook_all, configure_webhook_one
from infrahub.workflows.catalogue import WEBHOOK_PROCESS, worker_pools
from infrahub.workflows.initialization import setup_worker_pools

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from prefect.events.actions import RunDeployment

    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestWebhookTasks(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        register_core_schema: SchemaBranch,
        client: InfrahubClient,
        prefect_test_fixture,
    ) -> None:
        pass

    @pytest.fixture(scope="class")
    async def prefect_client(self, prefect_test_fixture) -> AsyncGenerator[PrefectClient, None]:
        async with get_client(sync_client=False) as client:
            yield client

    @pytest.fixture(scope="class")
    async def webhook_deployment(self, db: InfrahubDatabase, prefect_client: PrefectClient) -> None:
        await setup_worker_pools(client=prefect_client)
        await WEBHOOK_PROCESS.save(client=prefect_client, work_pool=worker_pools[0])

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
        webhook = await Node.init(schema=InfrahubKind.CUSTOMWEBHOOK, db=db)
        await webhook.new(
            db=db,
            name="Webhook2",
            url="https://url.mock",
            validate_certificates=False,
            event_type="infrahub.branch.created",
            branch_scope="all_branches",
        )
        await webhook.save(db=db)
        return webhook

    async def test_configure_one(
        self, db: InfrahubDatabase, service, prefect_client: PrefectClient, webhook1: Node, webhook_deployment
    ) -> None:
        await configure_webhook_one(event_data={"node_id": webhook1.id}, service=service)

        name = "webhook::Webhook1"
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

    async def test_configure_all(
        self,
        db: InfrahubDatabase,
        service,
        prefect_client: PrefectClient,
        webhook1: Node,
        webhook2: Node,
        webhook_deployment,
    ) -> None:
        await configure_webhook_all(service=service)

        automations = await prefect_client.read_automations()
        automations_by_name = {automation.name: automation for automation in automations}

        assert "webhook::Webhook1" in automations_by_name.keys()
        assert "webhook::Webhook2" in automations_by_name.keys()

        automation = automations_by_name["webhook::Webhook2"]
        assert len(automation.actions) == 1
        action: RunDeployment = automation.actions[0]  # type: ignore[assignment]
        assert action.parameters
        assert "webhook_id" in action.parameters.keys()
        assert action.parameters["webhook_id"] == webhook2.id
        assert "webhook_kind" in action.parameters.keys()
        assert action.parameters["webhook_kind"] == "CoreCustomWebhook"
