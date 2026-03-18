from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.webhook.constants import CACHE_KEY_PREFIX
from infrahub.webhook.tasks.invalidate import invalidate_webhook_headers
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache


class TestWebhookInvalidateHeaders(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def keyvalue_header(self, db: InfrahubDatabase, register_core_schema: None) -> Node:
        kv = await Node.init(schema=InfrahubKind.STATICKEYVALUE, db=db)
        await kv.new(db=db, name="auth-header", key="Authorization", value="Bearer secret-token")
        await kv.save(db=db)
        return kv

    @pytest.fixture(scope="class")
    async def webhook_with_headers(
        self, db: InfrahubDatabase, keyvalue_header: Node, register_core_schema: None
    ) -> Node:
        webhook = await Node.init(schema=InfrahubKind.STANDARDWEBHOOK, db=db)
        await webhook.new(
            db=db,
            name="WebhookWithHeaders",
            url="https://example.com/hook",
            shared_key="secret",
            validate_certificates=False,
            event_type="infrahub.branch.created",
            branch_scope="all_branches",
            headers=[keyvalue_header],
        )
        await webhook.save(db=db)
        return webhook

    async def test_invalidate_headers_clears_cache(
        self,
        db: InfrahubDatabase,
        memory_cache: MemoryCache,
        keyvalue_header: Node,
        webhook_with_headers: Node,
        webhook_deployment: None,
    ) -> None:
        cache_key = f"{CACHE_KEY_PREFIX}:{webhook_with_headers.id}"
        await memory_cache.set(key=cache_key, value='{"cached": true}')
        assert await memory_cache.get(key=cache_key) is not None

        await invalidate_webhook_headers(
            event_type="infrahub.node.updated",
            event_data={"node_id": keyvalue_header.id},
        )

        assert await memory_cache.get(key=cache_key) is None

    async def test_invalidate_headers_no_linked_webhooks(
        self,
        db: InfrahubDatabase,
        memory_cache: MemoryCache,
        webhook_with_headers: Node,
        webhook_deployment: None,
    ) -> None:
        cache_key = f"{CACHE_KEY_PREFIX}:{webhook_with_headers.id}"
        await memory_cache.set(key=cache_key, value='{"cached": true}')

        unlinked_kv = await Node.init(schema=InfrahubKind.STATICKEYVALUE, db=db)
        await unlinked_kv.new(db=db, name="unlinked-header", key="X-Unlinked", value="not-used")
        await unlinked_kv.save(db=db)

        await invalidate_webhook_headers(
            event_type="infrahub.node.updated",
            event_data={"node_id": unlinked_kv.id},
        )

        assert await memory_cache.get(key=cache_key) == '{"cached": true}'
