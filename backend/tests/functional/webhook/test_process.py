from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx
import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.webhook.models import EventContext
from infrahub.webhook.tasks import convert_node_to_webhook, webhook_process
from infrahub.workers.dependencies import build_http_service
from infrahub.workflows.constants import WorkflowTag
from tests.adapters.http import MemoryHTTP
from tests.helpers.test_app import TestInfrahubApp

from .conftest import BRANCH_CREATED_PAYLOAD, only_new_run, read_send_runs

if TYPE_CHECKING:
    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient

    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.task_manager.flow_run.prefect_client import FlowRunQuerying


WEBHOOK_TARGET_URL = "https://url.mock"


class TestWebhookProcess(TestInfrahubApp):
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
            "custom_headers": [],
            "webhook_type": "StandardWebhook",
        }

    async def test_convert_node_to_webhook_with_headers(
        self,
        db: InfrahubDatabase,
        webhook_with_headers: Node,
        client: InfrahubClient,
    ) -> None:
        webhook = await client.get(
            kind=InfrahubKind.STANDARDWEBHOOK, id=webhook_with_headers.id, prefetch_relationships=True
        )
        converted_webhook = await convert_node_to_webhook(webhook_node=webhook, client=client)

        dumped = converted_webhook.model_dump()
        assert sorted(dumped.pop("custom_headers"), key=lambda h: h.get("key", "")) == sorted(
            [
                {"key": "X-Custom-Token", "value": "secret123", "kind": "static"},
                {"key": "X-Env-Key", "value": "MY_ENV_VAR", "kind": "environment"},
            ],
            key=lambda h: h.get("key", ""),
        )
        assert dumped == {
            "name": "WebhookWithHeaders",
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
            "custom_headers": [],
            "webhook_type": "TransformWebhook",
        }

    async def test_process_standard_webhook_success(
        self,
        db: InfrahubDatabase,
        flow_run_querier: FlowRunQuerying,
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
            before = {str(run.id) for run in await read_send_runs(flow_run_querier)}
            await webhook_process(
                webhook_id=webhook1.id,
                webhook_name="Webhook1",
                webhook_kind=InfrahubKind.STANDARDWEBHOOK,
                event_id="ce3b7013-4abb-4945-89de-1f56da4ff636",
                event_type="infrahub.branch.created",
                event_occured_at="2025-02-28T08:37:09.969Z",
                event_payload=BRANCH_CREATED_PAYLOAD,
            )

        run = only_new_run(await read_send_runs(flow_run_querier), before)
        assert WorkflowTag.RELATED_NODE.render(identifier=webhook1.id) in run.tags

    async def test_process_webhook_failure_is_classified(
        self,
        db: InfrahubDatabase,
        webhook1: Node,
        webhook_deployment: None,
        dependency_provider: Provider,
        immediate_webhook_retries: None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # One representative case is enough here: per-class classification is covered by the unit tests;
        # this asserts the classifier is wired into the send flow and the run ends in a clean failed
        # state carrying the reason and remediation, without a stacktrace.
        http = MemoryHTTP()
        http.add_post_response(
            url=WEBHOOK_TARGET_URL,
            response=httpx.Response(request=httpx.Request(method="POST", url=WEBHOOK_TARGET_URL), status_code=404),
        )

        with (
            dependency_provider.scope(build_http_service, lambda: http),
            caplog.at_level(logging.INFO, logger="prefect.task_runs"),
            caplog.at_level(logging.INFO, logger="prefect.flow_runs"),
        ):
            state = await webhook_process(
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

        assert state.is_failed()
        assert (
            state.message
            == "The target responded with HTTP 404. The target rejected the request; check the URL and authentication."
        )
        # The classified failure is reported without a stacktrace: neither the send task nor the send
        # flow leaks a traceback-bearing record for the transport error.
        assert [record for record in caplog.records if record.exc_info] == []

    async def test_process_webhook_unexpected_error_crashes(
        self,
        db: InfrahubDatabase,
        webhook1: Node,
        webhook_deployment: None,
        dependency_provider: Provider,
        immediate_webhook_retries: None,
    ) -> None:
        http = MemoryHTTP()
        http.add_post_response(url=WEBHOOK_TARGET_URL, response=RuntimeError("boom"))

        with (
            pytest.raises(RuntimeError, match=r"^boom$"),
            dependency_provider.scope(build_http_service, lambda: http),
        ):
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

        payload = await webhook.compute_payload(data={}, context=context, client=client)

        assert payload == {
            "ACCOUNT_ID": "182853f2-3a43-c7f9-3e84-c5152eff4b17",
            "BRANCH": None,
            "DATA": {},
            "EVENT": "infrahub.branch.created",
            "ID": "ce3b7013-4abb-4945-89de-1f56da4ff636",
            "OCCURED_AT": "2025-02-28T08:37:09.969Z",
        }
