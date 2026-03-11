from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import httpx
import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.webhook.tasks import convert_node_to_webhook, webhook_process
from tests.adapters.http import MemoryHTTP
from tests.helpers.test_app import TestInfrahubApp

from .conftest import BRANCH_CREATED_PAYLOAD

if TYPE_CHECKING:
    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase


class HeaderCapturingHTTP(MemoryHTTP):
    """MemoryHTTP variant that records headers sent with each POST request."""

    def __init__(self) -> None:
        super().__init__()
        self.last_post_headers: dict[str, Any] | None = None

    async def post(
        self,
        url: str,
        data: Any | None = None,
        json: Any | None = None,
        headers: dict[str, Any] | None = None,
        verify: bool | None = None,
    ) -> httpx.Response:
        self.last_post_headers = headers
        return await super().post(url=url, data=data, json=json, headers=headers, verify=verify)


class TestWebhookHeaders(TestInfrahubApp):
    """Functional tests for custom HTTP headers on webhooks (T011, T018, T019, T021)."""

    # --- Fixtures: Key-Value nodes ---

    @pytest.fixture(scope="class")
    async def password_header(self, db: InfrahubDatabase, initial_dataset: None) -> Node:
        kv = await Node.init(schema=InfrahubKind.KEYVALUEPASSWORD, db=db)
        await kv.new(
            db=db,
            name="auth-token-header",
            key="Authorization",
            value="Bearer test-token-abc123",
        )
        await kv.save(db=db)
        return kv

    @pytest.fixture(scope="class")
    async def static_header(self, db: InfrahubDatabase, initial_dataset: None) -> Node:
        kv = await Node.init(schema=InfrahubKind.KEYVALUESTATIC, db=db)
        await kv.new(
            db=db,
            name="source-system-header",
            key="X-Source-System",
            value="infrahub",
        )
        await kv.save(db=db)
        return kv

    @pytest.fixture(scope="class")
    async def env_var_header(self, db: InfrahubDatabase, initial_dataset: None) -> Node:
        kv = await Node.init(schema=InfrahubKind.KEYVALUEENVIRONMENTVARIABLE, db=db)
        await kv.new(
            db=db,
            name="vault-api-key-header",
            key="X-API-Key",
            value="VAULT_API_KEY",
        )
        await kv.save(db=db)
        return kv

    @pytest.fixture(scope="class")
    async def shared_header(self, db: InfrahubDatabase, initial_dataset: None) -> Node:
        kv = await Node.init(schema=InfrahubKind.KEYVALUEPASSWORD, db=db)
        await kv.new(
            db=db,
            name="shared-auth-header",
            key="X-Shared-Auth",
            value="Bearer shared-token",
        )
        await kv.save(db=db)
        return kv

    # --- Fixtures: Webhooks with headers ---

    @pytest.fixture(scope="class")
    async def webhook_with_password_header(
        self, db: InfrahubDatabase, initial_dataset: None, password_header: Node
    ) -> Node:
        webhook = await Node.init(schema=InfrahubKind.STANDARDWEBHOOK, db=db)
        await webhook.new(
            db=db,
            name="WebhookWithAuthHeader",
            url="https://url.mock",
            shared_key="secret-key",
            validate_certificates=False,
            event_type="infrahub.branch.created",
            branch_scope="all_branches",
            headers=[password_header],
        )
        await webhook.save(db=db)
        return webhook

    @pytest.fixture(scope="class")
    async def webhook_with_static_header(
        self, db: InfrahubDatabase, initial_dataset: None, static_header: Node
    ) -> Node:
        webhook = await Node.init(schema=InfrahubKind.STANDARDWEBHOOK, db=db)
        await webhook.new(
            db=db,
            name="WebhookWithStaticHeader",
            url="https://url.mock",
            shared_key="secret-key",
            validate_certificates=False,
            event_type="infrahub.branch.created",
            branch_scope="all_branches",
            headers=[static_header],
        )
        await webhook.save(db=db)
        return webhook

    @pytest.fixture(scope="class")
    async def webhook_with_env_header(self, db: InfrahubDatabase, initial_dataset: None, env_var_header: Node) -> Node:
        webhook = await Node.init(schema=InfrahubKind.STANDARDWEBHOOK, db=db)
        await webhook.new(
            db=db,
            name="WebhookWithEnvHeader",
            url="https://url.mock",
            shared_key="secret-key",
            validate_certificates=False,
            event_type="infrahub.branch.created",
            branch_scope="all_branches",
            headers=[env_var_header],
        )
        await webhook.save(db=db)
        return webhook

    @pytest.fixture(scope="class")
    async def webhook_a_shared(self, db: InfrahubDatabase, initial_dataset: None, shared_header: Node) -> Node:
        webhook = await Node.init(schema=InfrahubKind.STANDARDWEBHOOK, db=db)
        await webhook.new(
            db=db,
            name="WebhookA-Shared",
            url="https://url.mock",
            shared_key="secret-a",
            validate_certificates=False,
            event_type="infrahub.branch.created",
            branch_scope="all_branches",
            headers=[shared_header],
        )
        await webhook.save(db=db)
        return webhook

    @pytest.fixture(scope="class")
    async def webhook_b_shared(self, db: InfrahubDatabase, initial_dataset: None, shared_header: Node) -> Node:
        webhook = await Node.init(schema=InfrahubKind.STANDARDWEBHOOK, db=db)
        await webhook.new(
            db=db,
            name="WebhookB-Shared",
            url="https://url.mock",
            shared_key="secret-b",
            validate_certificates=False,
            event_type="infrahub.branch.created",
            branch_scope="all_branches",
            headers=[shared_header],
        )
        await webhook.save(db=db)
        return webhook

    # --- T011: Password header tests ---

    async def test_convert_node_includes_custom_headers(
        self,
        db: InfrahubDatabase,
        webhook_with_password_header: Node,
        client: InfrahubClient,
    ) -> None:
        """T011: Verify convert_node_to_webhook fetches headers from the relationship."""
        webhook_node = await client.get(kind=InfrahubKind.STANDARDWEBHOOK, id=webhook_with_password_header.id)
        converted = await convert_node_to_webhook(webhook_node=webhook_node, client=client)

        assert len(converted.custom_headers) == 1
        header = converted.custom_headers[0]
        assert header.key == "Authorization"
        assert header.value == "Bearer test-token-abc123"
        assert header.header_type == "password"

    async def test_process_webhook_sends_password_header(
        self,
        db: InfrahubDatabase,
        webhook_with_password_header: Node,
        webhook_deployment: None,
        dependency_provider: Provider,
    ) -> None:
        """T011: Verify the webhook HTTP request includes the custom authentication header."""
        from infrahub.workers.dependencies import build_http_service

        http = HeaderCapturingHTTP()
        http.add_post_response(
            url="https://url.mock",
            response=httpx.Response(request=httpx.Request(method="POST", url="https://url.mock"), status_code=200),
        )
        with dependency_provider.scope(build_http_service, lambda: http):
            await webhook_process(
                webhook_id=webhook_with_password_header.id,
                webhook_name="WebhookWithAuthHeader",
                webhook_kind="CoreStandardWebhook",
                event_id="ce3b7013-4abb-4945-89de-1f56da4ff636",
                event_type="infrahub.branch.created",
                event_occured_at="2025-02-28T08:37:09.969Z",
                event_payload=BRANCH_CREATED_PAYLOAD,
            )

        assert http.last_post_headers is not None
        assert http.last_post_headers["Authorization"] == "Bearer test-token-abc123"
        assert http.last_post_headers["Content-Type"] == "application/json"
        assert "webhook-signature" in http.last_post_headers

    # --- T021: Static header test ---

    async def test_process_webhook_sends_static_header(
        self,
        db: InfrahubDatabase,
        webhook_with_static_header: Node,
        webhook_deployment: None,
        dependency_provider: Provider,
    ) -> None:
        """T021: Verify the webhook HTTP request includes the static header with literal value."""
        from infrahub.workers.dependencies import build_http_service

        http = HeaderCapturingHTTP()
        http.add_post_response(
            url="https://url.mock",
            response=httpx.Response(request=httpx.Request(method="POST", url="https://url.mock"), status_code=200),
        )
        with dependency_provider.scope(build_http_service, lambda: http):
            await webhook_process(
                webhook_id=webhook_with_static_header.id,
                webhook_name="WebhookWithStaticHeader",
                webhook_kind="CoreStandardWebhook",
                event_id="ce3b7013-4abb-4945-89de-1f56da4ff636",
                event_type="infrahub.branch.created",
                event_occured_at="2025-02-28T08:37:09.969Z",
                event_payload=BRANCH_CREATED_PAYLOAD,
            )

        assert http.last_post_headers is not None
        assert http.last_post_headers["X-Source-System"] == "infrahub"

    # --- Env var header tests ---

    async def test_process_webhook_resolves_env_var_header(
        self,
        db: InfrahubDatabase,
        webhook_with_env_header: Node,
        webhook_deployment: None,
        dependency_provider: Provider,
    ) -> None:
        """Verify the env var header resolves from os.environ at send time."""
        from infrahub.workers.dependencies import build_http_service

        http = HeaderCapturingHTTP()
        http.add_post_response(
            url="https://url.mock",
            response=httpx.Response(request=httpx.Request(method="POST", url="https://url.mock"), status_code=200),
        )
        with (
            patch.dict(os.environ, {"VAULT_API_KEY": "resolved-secret-value"}),
            dependency_provider.scope(build_http_service, lambda: http),
        ):
            await webhook_process(
                webhook_id=webhook_with_env_header.id,
                webhook_name="WebhookWithEnvHeader",
                webhook_kind="CoreStandardWebhook",
                event_id="ce3b7013-4abb-4945-89de-1f56da4ff636",
                event_type="infrahub.branch.created",
                event_occured_at="2025-02-28T08:37:09.969Z",
                event_payload=BRANCH_CREATED_PAYLOAD,
            )

        assert http.last_post_headers is not None
        assert http.last_post_headers["X-API-Key"] == "resolved-secret-value"

    async def test_process_webhook_skips_missing_env_var_header(
        self,
        db: InfrahubDatabase,
        webhook_with_env_header: Node,
        webhook_deployment: None,
        dependency_provider: Provider,
    ) -> None:
        """Verify missing env var header is skipped; webhook still sends successfully."""
        from infrahub.workers.dependencies import build_http_service

        http = HeaderCapturingHTTP()
        http.add_post_response(
            url="https://url.mock",
            response=httpx.Response(request=httpx.Request(method="POST", url="https://url.mock"), status_code=200),
        )
        with (
            patch.dict(os.environ, {}, clear=False),
            dependency_provider.scope(build_http_service, lambda: http),
        ):
            os.environ.pop("VAULT_API_KEY", None)
            await webhook_process(
                webhook_id=webhook_with_env_header.id,
                webhook_name="WebhookWithEnvHeader",
                webhook_kind="CoreStandardWebhook",
                event_id="ce3b7013-4abb-4945-89de-1f56da4ff636",
                event_type="infrahub.branch.created",
                event_occured_at="2025-02-28T08:37:09.969Z",
                event_payload=BRANCH_CREATED_PAYLOAD,
            )

        assert http.last_post_headers is not None
        assert "X-API-Key" not in http.last_post_headers
        assert http.last_post_headers["Content-Type"] == "application/json"

    # --- T018: Shared header across webhooks ---

    async def test_shared_header_sent_by_both_webhooks(
        self,
        db: InfrahubDatabase,
        webhook_a_shared: Node,
        webhook_b_shared: Node,
        webhook_deployment: None,
        dependency_provider: Provider,
    ) -> None:
        """T018: Verify both webhooks include the shared header."""
        from infrahub.workers.dependencies import build_http_service

        for webhook_node, name in [(webhook_a_shared, "WebhookA-Shared"), (webhook_b_shared, "WebhookB-Shared")]:
            http = HeaderCapturingHTTP()
            http.add_post_response(
                url="https://url.mock",
                response=httpx.Response(request=httpx.Request(method="POST", url="https://url.mock"), status_code=200),
            )
            with dependency_provider.scope(build_http_service, lambda _http=http: _http):
                await webhook_process(
                    webhook_id=webhook_node.id,
                    webhook_name=name,
                    webhook_kind="CoreStandardWebhook",
                    event_id="ce3b7013-4abb-4945-89de-1f56da4ff636",
                    event_type="infrahub.branch.created",
                    event_occured_at="2025-02-28T08:37:09.969Z",
                    event_payload=BRANCH_CREATED_PAYLOAD,
                )

            assert http.last_post_headers is not None
            assert http.last_post_headers["X-Shared-Auth"] == "Bearer shared-token", (
                f"Webhook {name} missing shared header"
            )

    # --- T019: Unlink header from one webhook ---

    async def test_unlinked_header_not_sent(
        self,
        db: InfrahubDatabase,
        webhook_a_shared: Node,
        webhook_b_shared: Node,
        client: InfrahubClient,
        webhook_deployment: None,
        dependency_provider: Provider,
    ) -> None:
        """T019: Removing a header from one webhook does not affect the other."""
        from infrahub.workers.dependencies import build_cache, build_http_service

        # Remove header from webhook_a
        webhook_a_node = await client.get(kind=InfrahubKind.STANDARDWEBHOOK, id=webhook_a_shared.id)
        await webhook_a_node.headers.fetch()
        for peer in list(webhook_a_node.headers.peers):
            webhook_a_node.headers.remove(peer.id)
        await webhook_a_node.save()

        # Invalidate cached webhook data so webhook_process re-fetches from DB
        cache = await build_cache()
        await cache.delete(key=f"webhook:{webhook_a_shared.id}")
        await cache.delete(key=f"webhook:{webhook_b_shared.id}")

        # Webhook A should no longer send the header
        http_a = HeaderCapturingHTTP()
        http_a.add_post_response(
            url="https://url.mock",
            response=httpx.Response(request=httpx.Request(method="POST", url="https://url.mock"), status_code=200),
        )
        with dependency_provider.scope(build_http_service, lambda: http_a):
            await webhook_process(
                webhook_id=webhook_a_shared.id,
                webhook_name="WebhookA-Shared",
                webhook_kind="CoreStandardWebhook",
                event_id="ce3b7013-4abb-4945-89de-1f56da4ff636",
                event_type="infrahub.branch.created",
                event_occured_at="2025-02-28T08:37:09.969Z",
                event_payload=BRANCH_CREATED_PAYLOAD,
            )

        assert http_a.last_post_headers is not None
        assert "X-Shared-Auth" not in http_a.last_post_headers

        # Webhook B should still send the header
        http_b = HeaderCapturingHTTP()
        http_b.add_post_response(
            url="https://url.mock",
            response=httpx.Response(request=httpx.Request(method="POST", url="https://url.mock"), status_code=200),
        )
        with dependency_provider.scope(build_http_service, lambda: http_b):
            await webhook_process(
                webhook_id=webhook_b_shared.id,
                webhook_name="WebhookB-Shared",
                webhook_kind="CoreStandardWebhook",
                event_id="ce3b7013-4abb-4945-89de-1f56da4ff636",
                event_type="infrahub.branch.created",
                event_occured_at="2025-02-28T08:37:09.969Z",
                event_payload=BRANCH_CREATED_PAYLOAD,
            )

        assert http_b.last_post_headers is not None
        assert http_b.last_post_headers["X-Shared-Auth"] == "Bearer shared-token"
