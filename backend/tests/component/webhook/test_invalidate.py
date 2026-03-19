from __future__ import annotations

import logging
from contextlib import ExitStack
from typing import TYPE_CHECKING
from unittest.mock import patch

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.webhook.constants import CACHE_KEY_PREFIX
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
    if headers is not None:
        kwargs["headers"] = headers
    await webhook.new(db=db, **kwargs)
    await webhook.save(db=db)
    return webhook


def _invalidation_patches(db: InfrahubDatabase, cache: MemoryCache):
    """Common patches for running invalidate_webhook_headers.fn() in tests."""

    async def fake_get_database() -> InfrahubDatabase:
        return db

    return (
        patch("infrahub.webhook.tasks.cache.get_cache", return_value=cache),
        patch("infrahub.webhook.tasks.invalidate.get_database", side_effect=fake_get_database),
        patch("infrahub.webhook.tasks.invalidate.get_run_logger", return_value=logging.getLogger("test")),
        patch("infrahub.webhook.tasks.cache.get_run_logger", return_value=logging.getLogger("test")),
    )


async def _run_invalidation(db: InfrahubDatabase, cache: MemoryCache, keyvalue_id: str) -> None:
    with ExitStack() as stack:
        for p in _invalidation_patches(db, cache):
            stack.enter_context(p)
        await invalidate_webhook_headers.fn(event_data={"node_id": keyvalue_id})


class TestCacheInvalidationFlow:
    async def test_finds_linked_webhook(
        self, db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
    ) -> None:
        default_branch.update_schema_hash()
        kv = await _create_keyvalue(db, default_branch, "x-api-key", "X-Api-Key", "abc123")
        webhook = await _create_webhook(db, default_branch, "hook-1", headers=[kv])

        cache = MemoryCache()
        await cache.set(key=f"{CACHE_KEY_PREFIX}:{webhook.id}", value='{"cached": true}')

        # Act
        await _run_invalidation(db, cache, kv.id)

        assert await cache.get(f"{CACHE_KEY_PREFIX}:{webhook.id}") is None

    async def test_returns_empty_for_unlinked_keyvalue(
        self, db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
    ) -> None:
        default_branch.update_schema_hash()
        kv = await _create_keyvalue(db, default_branch, "x-unused", "X-Unused", "unused")

        cache = MemoryCache()
        await cache.set(key=f"{CACHE_KEY_PREFIX}:some-id", value='{"cached": true}')

        # Act
        await _run_invalidation(db, cache, kv.id)

        assert await cache.get(f"{CACHE_KEY_PREFIX}:some-id") == '{"cached": true}'

    async def test_invalidate_removes_linked_webhook_cache_keys(
        self, db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
    ) -> None:
        default_branch.update_schema_hash()
        kv = await _create_keyvalue(db, default_branch, "x-token", "X-Token", "tok123")
        wh1 = await _create_webhook(db, default_branch, "hook-x", headers=[kv])
        wh2 = await _create_webhook(db, default_branch, "hook-y", headers=[kv])

        cache = MemoryCache()
        await cache.set(key=f"{CACHE_KEY_PREFIX}:{wh1.id}", value='{"cached": true}')
        await cache.set(key=f"{CACHE_KEY_PREFIX}:{wh2.id}", value='{"cached": true}')
        await cache.set(key=f"{CACHE_KEY_PREFIX}:unrelated-id", value='{"cached": true}')

        # Act
        await _run_invalidation(db, cache, kv.id)

        assert await cache.get(f"{CACHE_KEY_PREFIX}:{wh1.id}") is None
        assert await cache.get(f"{CACHE_KEY_PREFIX}:{wh2.id}") is None
        assert await cache.get(f"{CACHE_KEY_PREFIX}:unrelated-id") == '{"cached": true}'

    async def test_invalidates_webhook_with_multiple_headers(
        self, db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
    ) -> None:
        default_branch.update_schema_hash()
        kv1 = await _create_keyvalue(db, default_branch, "x-header-1", "X-Header-1", "val1")
        kv2 = await _create_keyvalue(db, default_branch, "x-header-2", "X-Header-2", "val2")
        webhook = await _create_webhook(db, default_branch, "hook-multi", headers=[kv1, kv2])

        cache = MemoryCache()
        await cache.set(key=f"{CACHE_KEY_PREFIX}:{webhook.id}", value='{"cached": true}')

        # Act
        await _run_invalidation(db, cache, kv1.id)

        assert await cache.get(f"{CACHE_KEY_PREFIX}:{webhook.id}") is None

    async def test_excluded_when_all_headers_deleted(
        self, db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
    ) -> None:
        """When all headers are deleted from a webhook, the deleted edges should be filtered out."""
        default_branch.update_schema_hash()
        kv = await _create_keyvalue(db, default_branch, "x-removed", "X-Removed", "gone")
        webhook = await _create_webhook(db, default_branch, "hook-remove", headers=[kv])

        # Delete all headers from the webhook
        webhook_refreshed = await NodeManager.get_one(db=db, branch=default_branch, id=webhook.id)

        cache = MemoryCache()
        await cache.set(key=f"{CACHE_KEY_PREFIX}:{webhook.id}", value='{"cached": true}')

        await webhook_refreshed.headers.delete(db=db)

        # Act
        await _run_invalidation(db, cache, kv.id)

        assert await cache.get(f"{CACHE_KEY_PREFIX}:{webhook.id}") == '{"cached": true}'

    async def test_partial_removal_still_finds_remaining(
        self, db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
    ) -> None:
        """When one of two webhooks has its headers deleted, only the remaining one is found. Cache deletion should be
        managed through the configure flow related to webhooks headers, not this one"""
        default_branch.update_schema_hash()
        kv = await _create_keyvalue(db, default_branch, "x-shared-del", "X-Shared-Del", "shared")
        wh_kept = await _create_webhook(db, default_branch, "hook-kept", headers=[kv])
        wh_removed = await _create_webhook(db, default_branch, "hook-removed", headers=[kv])

        wh_removed_refreshed = await NodeManager.get_one(db=db, branch=default_branch, id=wh_removed.id)

        cache = MemoryCache()
        await cache.set(key=f"{CACHE_KEY_PREFIX}:{wh_kept.id}", value='{"cached": true}')
        await cache.set(key=f"{CACHE_KEY_PREFIX}:{wh_removed.id}", value='{"cached": true}')

        # Delete headers from only one webhook
        await wh_removed_refreshed.headers.delete(db=db)

        await _run_invalidation(db, cache, kv.id)

        assert await cache.get(f"{CACHE_KEY_PREFIX}:{wh_kept.id}") is None
        assert await cache.get(f"{CACHE_KEY_PREFIX}:{wh_removed.id}") == '{"cached": true}'
