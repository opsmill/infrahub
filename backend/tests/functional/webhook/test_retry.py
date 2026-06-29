from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import httpx
import pytest
from infrahub_sdk.graphql import Mutation

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


class TestWebhookRetry(TestInfrahubApp):
    async def test_retry_replays_frozen_payload_as_new_delivery(
        self,
        db: InfrahubDatabase,
        flow_run_querier: FlowRunQuerying,
        webhook1: Node,
        webhook_deployment: None,
        client: InfrahubClient,
        dependency_provider: Provider,
        immediate_webhook_retries: None,
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

            original = only_new_run(await read_send_runs(flow_run_querier), before)
            original_payload = original.parameters["payload"]
            seen = before | {str(original.id)}

            # The retry submits the delivery synchronously here, so the mock must stay in scope.
            mutation = Mutation(
                mutation="InfrahubTaskRetry",
                input_data={"data": {"id": str(original.id)}},
                query={"ok": None, "task": {"id": None}},
            )
            result = await client.execute_graphql(query=mutation.render())

        assert result["InfrahubTaskRetry"]["ok"] is True
        assert result["InfrahubTaskRetry"]["task"]["id"]

        # The retry produced a new, independent delivery replaying the frozen payload.
        post_runs = await read_send_runs(flow_run_querier)
        new_run = only_new_run(post_runs, seen)
        assert new_run.parameters["payload"] == original_payload

        # The original delivery is left untouched as an immutable record.
        unchanged = next(run for run in post_runs if str(run.id) == str(original.id))
        assert unchanged.parameters["payload"] == original_payload

    async def test_retry_in_progress_delivery_is_rejected(
        self,
        db: InfrahubDatabase,
        webhook1: Node,
        webhook_deployment: None,
        client: InfrahubClient,
        scheduled_send_run: FlowRun,
    ) -> None:
        mutation = Mutation(
            mutation="InfrahubTaskRetry",
            input_data={"data": {"id": str(scheduled_send_run.id)}},
            query={"ok": None, "task": {"id": None}},
        )
        with pytest.raises(Exception, match=r"Retry is unavailable: Delivery still in progress\."):
            await client.execute_graphql(query=mutation.render())

    async def test_retry_denied_without_permission(
        self,
        db: InfrahubDatabase,
        webhook1: Node,
        webhook_deployment: None,
        unprivileged_client: InfrahubClient,
        settled_send_run: FlowRun,
    ) -> None:
        mutation = Mutation(
            mutation="InfrahubTaskRetry",
            input_data={"data": {"id": str(settled_send_run.id)}},
            query={"ok": None, "task": {"id": None}},
        )
        with pytest.raises(Exception, match="You do not have the following permission"):
            await unprivileged_client.execute_graphql(query=mutation.render())

    async def test_retry_unknown_delivery_reports_no_longer_available(
        self,
        db: InfrahubDatabase,
        webhook1: Node,
        webhook_deployment: None,
        client: InfrahubClient,
    ) -> None:
        mutation = Mutation(
            mutation="InfrahubTaskRetry",
            input_data={"data": {"id": str(uuid4())}},
            query={"ok": None, "task": {"id": None}},
        )
        with pytest.raises(Exception, match="no longer available"):
            await client.execute_graphql(query=mutation.render())
