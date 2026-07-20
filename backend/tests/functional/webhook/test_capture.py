from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from infrahub.core.constants import InfrahubKind
from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter
from infrahub.task_manager.flow_run.reader import FlowRunReader
from infrahub.webhook.tasks import webhook_process
from infrahub.workers.dependencies import build_http_service
from tests.adapters.http import MemoryHTTP
from tests.helpers.test_app import TestInfrahubApp

from .conftest import BRANCH_CREATED_PAYLOAD, only_new_run, read_send_runs

if TYPE_CHECKING:
    from fast_depends import Provider
    from prefect.client.orchestration import PrefectClient

    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.task_manager.flow_run.prefect_client import FlowRunQuerying


WEBHOOK_TARGET_URL = "https://url.mock"
SHARED_KEY = "1234567890"


async def _latest_capture(prefect_client: PrefectClient, run_id: Any) -> dict[str, Any]:
    reader = FlowRunReader(client=PrefectClientAdapter(prefect_client))
    captures = await reader.read_http(flow_ids=[run_id])
    assert run_id in captures.data, "expected an http capture for the delivery"
    return captures.data[run_id]


class TestWebhookCapture(TestInfrahubApp):
    async def test_capture_present_on_success(
        self,
        db: InfrahubDatabase,
        prefect_client: PrefectClient,
        flow_run_querier: FlowRunQuerying,
        webhook1: Node,
        webhook_deployment: None,
        dependency_provider: Provider,
    ) -> None:
        http = MemoryHTTP()
        http.add_post_response(
            url=WEBHOOK_TARGET_URL,
            response=httpx.Response(
                request=httpx.Request(method="POST", url=WEBHOOK_TARGET_URL), status_code=200, text='{"ok": true}'
            ),
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

        run = only_new_run(await read_send_runs(flow_run_querier), before)
        capture = await _latest_capture(prefect_client, run.id)

        assert capture["request"]["url"] == WEBHOOK_TARGET_URL
        assert capture["response"]["status_code"] == 200
        assert capture["response"]["body"] == '{"ok": true}'
        assert capture["error"] is None
        # The signature is redacted at capture, so no raw secret is persisted.
        assert capture["request"]["headers"]["webhook-signature"] == "***"
        assert SHARED_KEY not in str(capture)

    async def test_capture_present_on_failure_with_classified_error(
        self,
        db: InfrahubDatabase,
        prefect_client: PrefectClient,
        flow_run_querier: FlowRunQuerying,
        webhook1: Node,
        webhook_deployment: None,
        dependency_provider: Provider,
        immediate_webhook_retries: None,
    ) -> None:
        http = MemoryHTTP()
        http.add_post_response(
            url=WEBHOOK_TARGET_URL,
            response=httpx.Response(
                request=httpx.Request(method="POST", url=WEBHOOK_TARGET_URL), status_code=500, text="server error"
            ),
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
                return_state=True,
            )

        run = only_new_run(await read_send_runs(flow_run_querier), before)
        capture = await _latest_capture(prefect_client, run.id)

        assert capture["error"]["status_class"] == "HTTP_SERVER_ERROR"
        assert capture["error"]["message"] == "The target responded with HTTP 500."
        assert capture["error"]["remediation"]
        assert capture["response"]["status_code"] == 500
        assert capture["request"]["url"] == WEBHOOK_TARGET_URL
        assert SHARED_KEY not in str(capture)
