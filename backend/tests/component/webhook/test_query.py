from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import patch

from infrahub.core.node import Node
from infrahub.webhook.query import KeyValueGetWebhooksQuery, KeyValueWebhookResult
from infrahub.webhook.tasks.invalidate import invalidate_webhook_headers
from tests.adapters.cache import MemoryCache

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def _create_keyvalue(db: InfrahubDatabase, branch: Branch, name: str, key: str, value: str) -> Node:
    kv = await Node.init(db=db, branch=branch, schema="CoreStaticKeyValue")
    await kv.new(db=db, name=name, key=key, value=value)
    await kv.save(db=db)
    return kv


async def _create_webhook(db: InfrahubDatabase, branch: Branch, name: str, headers: list[Node] | None = None) -> Node:
    webhook = await Node.init(db=db, branch=branch, schema="CoreStandardWebhook")
    kwargs: dict = {
        "name": name,
        "url": "https://example.com/hook",
        "shared_key": "secret",
    }
    if headers:
        kwargs["headers"] = headers
    await webhook.new(db=db, **kwargs)
    await webhook.save(db=db)
    return webhook


class TestKeyValueGetWebhooksQuery:
    async def test_finds_linked_webhook(
        self, db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
    ) -> None:
        default_branch.update_schema_hash()
        kv = await _create_keyvalue(db, default_branch, "x-api-key", "X-Api-Key", "abc123")
        webhook = await _create_webhook(db, default_branch, "hook-1", headers=[kv])

        query = await KeyValueGetWebhooksQuery.init(db=db, keyvalue_id=kv.id)
        await query.execute(db=db)
        results = query.get_data()

        assert results == KeyValueWebhookResult(webhook_uuids=frozenset({webhook.id}))

    async def test_returns_empty_for_unlinked_keyvalue(
        self, db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
    ) -> None:
        default_branch.update_schema_hash()
        kv = await _create_keyvalue(db, default_branch, "x-unused", "X-Unused", "unused")

        query = await KeyValueGetWebhooksQuery.init(db=db, keyvalue_id=kv.id)
        await query.execute(db=db)
        results = query.get_data()

        assert results == KeyValueWebhookResult(webhook_uuids=frozenset())

    async def test_returns_multiple_webhooks(
        self, db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
    ) -> None:
        default_branch.update_schema_hash()
        kv = await _create_keyvalue(db, default_branch, "x-shared", "X-Shared", "shared-val")
        wh1 = await _create_webhook(db, default_branch, "hook-a", headers=[kv])
        wh2 = await _create_webhook(db, default_branch, "hook-b", headers=[kv])

        query = await KeyValueGetWebhooksQuery.init(db=db, keyvalue_id=kv.id)
        await query.execute(db=db)
        results = query.get_data()

        assert results == KeyValueWebhookResult(webhook_uuids=frozenset({wh1.id, wh2.id}))

    async def test_no_duplicates(
        self, db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
    ) -> None:
        default_branch.update_schema_hash()
        kv1 = await _create_keyvalue(db, default_branch, "x-header-1", "X-Header-1", "val1")
        kv2 = await _create_keyvalue(db, default_branch, "x-header-2", "X-Header-2", "val2")
        webhook = await _create_webhook(db, default_branch, "hook-multi", headers=[kv1, kv2])

        query = await KeyValueGetWebhooksQuery.init(db=db, keyvalue_id=kv1.id)
        await query.execute(db=db)
        results = query.get_data()

        assert results == KeyValueWebhookResult(webhook_uuids=frozenset({webhook.id}))


class TestCacheInvalidationFlow:
    async def test_invalidate_removes_linked_webhook_cache_keys(
        self, db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
    ) -> None:
        default_branch.update_schema_hash()
        kv = await _create_keyvalue(db, default_branch, "x-token", "X-Token", "tok123")
        wh1 = await _create_webhook(db, default_branch, "hook-x", headers=[kv])
        wh2 = await _create_webhook(db, default_branch, "hook-y", headers=[kv])

        cache = MemoryCache()
        await cache.set(key=f"webhook:{wh1.id}", value='{"cached": true}')
        await cache.set(key=f"webhook:{wh2.id}", value='{"cached": true}')
        await cache.set(key="webhook:unrelated-id", value='{"cached": true}')

        async def fake_get_database() -> InfrahubDatabase:
            return db

        with (
            patch("infrahub.webhook.tasks.cache.get_cache", return_value=cache),
            patch("infrahub.webhook.tasks.invalidate.get_database", side_effect=fake_get_database),
            patch("infrahub.webhook.tasks.invalidate.get_run_logger", return_value=logging.getLogger("test")),
            patch("infrahub.webhook.tasks.cache.get_run_logger", return_value=logging.getLogger("test")),
        ):
            await invalidate_webhook_headers.fn(event_data={"node_id": kv.id})

        assert await cache.get(f"webhook:{wh1.id}") is None
        assert await cache.get(f"webhook:{wh2.id}") is None
        assert await cache.get("webhook:unrelated-id") == '{"cached": true}'
