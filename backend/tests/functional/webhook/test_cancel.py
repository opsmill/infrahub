from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import httpx
import pytest
from infrahub_sdk.graphql import Mutation
from prefect.client.schemas.objects import StateType

from infrahub.core.constants import InfrahubKind
from infrahub.webhook.tasks import webhook_process
from infrahub.workers.dependencies import build_http_service
from tests.adapters.http import MemoryHTTP
from tests.helpers.test_app import TestInfrahubApp

from .conftest import BRANCH_CREATED_PAYLOAD, only_new_run, read_send_runs

if TYPE_CHECKING:
    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient
    from prefect.client.schemas.objects import FlowRun

    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.task_manager.flow_run.prefect_client import FlowRunQuerying


WEBHOOK_TARGET_URL = "https://url.mock"


class TestWebhookCancel(TestInfrahubApp):
    async def test_cancel_in_progress_delivery_settles_to_cancelled(
        self,
        db: InfrahubDatabase,
        flow_run_querier: FlowRunQuerying,
        webhook1: Node,
        webhook_deployment: None,
        client: InfrahubClient,
        scheduled_send_run: FlowRun,
    ) -> None:
        mutation = Mutation(
            mutation="InfrahubTaskCancel",
            input_data={"data": {"id": str(scheduled_send_run.id)}},
            query={"ok": None, "task": {"id": None}},
        )
        result = await client.execute_graphql(query=mutation.render())

        assert result["InfrahubTaskCancel"]["ok"] is True

        # A delivery with no running infrastructure has its cancellation routed to a terminal state.
        settled = next(
            run for run in await read_send_runs(flow_run_querier) if str(run.id) == str(scheduled_send_run.id)
        )
        assert settled.state_type == StateType.CANCELLED

    async def test_cancel_settled_delivery_is_rejected(
        self,
        db: InfrahubDatabase,
        flow_run_querier: FlowRunQuerying,
        webhook1: Node,
        webhook_deployment: None,
        client: InfrahubClient,
        dependency_provider: Provider,
    ) -> None:
        http = MemoryHTTP()
        http.add_post_response(
            url=WEBHOOK_TARGET_URL,
            response=httpx.Response(request=httpx.Request(method="POST", url=WEBHOOK_TARGET_URL), status_code=200),
        )

        with dependency_provider.scope(build_http_service, lambda: http):
            before = {str(run.id) for run in await read_send_runs(flow_run_querier)}
            await webhook_process(
                webhook_id=webhook1.id,
                webhook_name="Webhook1",
                webhook_kind=InfrahubKind.STANDARDWEBHOOK,
                branch_name="main",
                event_id="ce3b7013-4abb-4945-89de-1f56da4ff636",
                event_type="infrahub.branch.created",
                event_occured_at="2025-02-28T08:37:09.969Z",
                event_payload=BRANCH_CREATED_PAYLOAD,
            )

        # Select the delivery this test just created, ignoring runs left by other tests in the session.
        delivery = only_new_run(await read_send_runs(flow_run_querier), before)

        mutation = Mutation(
            mutation="InfrahubTaskCancel",
            input_data={"data": {"id": str(delivery.id)}},
            query={"ok": None, "task": {"id": None}},
        )
        with pytest.raises(Exception, match="Cancel is unavailable"):
            await client.execute_graphql(query=mutation.render())

    async def test_cancel_denied_without_permission(
        self,
        db: InfrahubDatabase,
        webhook1: Node,
        webhook_deployment: None,
        unprivileged_client: InfrahubClient,
        scheduled_send_run: FlowRun,
    ) -> None:
        mutation = Mutation(
            mutation="InfrahubTaskCancel",
            input_data={"data": {"id": str(scheduled_send_run.id)}},
            query={"ok": None, "task": {"id": None}},
        )
        with pytest.raises(Exception, match="You do not have the following permission"):
            await unprivileged_client.execute_graphql(query=mutation.render())

    async def test_cancel_unknown_delivery_reports_no_longer_available(
        self,
        db: InfrahubDatabase,
        webhook1: Node,
        webhook_deployment: None,
        client: InfrahubClient,
    ) -> None:
        mutation = Mutation(
            mutation="InfrahubTaskCancel",
            input_data={"data": {"id": str(uuid4())}},
            query={"ok": None, "task": {"id": None}},
        )
        with pytest.raises(Exception, match="no longer available"):
            await client.execute_graphql(query=mutation.render())
