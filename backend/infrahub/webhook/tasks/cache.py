from __future__ import annotations

from typing import TYPE_CHECKING

from prefect import task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

from infrahub.workers.dependencies import get_cache

from ..constants import CACHE_KEY_PREFIX

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet


@task(name="webhook-invalidate-cache", task_run_name="Invalidate webhook cache", cache_policy=NONE)
async def invalidate_webhook_cache(webhook_ids: AbstractSet[str]) -> None:
    """Delete cached webhook data for the given webhook IDs."""
    cache = await get_cache()
    log = get_run_logger()
    for wid in webhook_ids:
        await cache.delete(key=f"{CACHE_KEY_PREFIX}:{wid}")
    log.info(f"Invalidated cache for {len(webhook_ids)} webhook(s)")
