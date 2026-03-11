from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.webhook.models import EventContext
from infrahub.webhook.tasks import convert_node_to_webhook, webhook_process
from tests.adapters.http import MemoryHTTP
from tests.helpers.test_app import TestInfrahubApp

from .conftest import BRANCH_CREATED_PAYLOAD

if TYPE_CHECKING:
    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient
    from prefect.client.orchestration import PrefectClient

    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


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
            "custom_headers": [],
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
        from infrahub.workers.dependencies import build_http_service

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
        from infrahub.workers.dependencies import build_http_service

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
