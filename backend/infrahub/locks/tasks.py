from __future__ import annotations

from typing import TYPE_CHECKING

from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.orchestration import get_client as get_prefect_client
from prefect.logging import get_run_logger

from infrahub import config
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.lock import LOCK_PREFIX
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow
from infrahub.workflows.locks import PER_WORKER_GCLS

if TYPE_CHECKING:
    from logging import Logger


@flow(
    name="clean-up-deadlocks",
    flow_run_name="Clean up deadlocks",
)
async def clean_up_deadlocks(service: InfrahubServices) -> None:
    """Remove stale distributed locks left behind by inactive workers"""
    keys = await service.cache.list_keys(filter_pattern=f"{LOCK_PREFIX}*")
    if not keys:
        return

    log = get_run_logger()
    values = await service.cache.get_values(keys=keys)
    workers = await service.component.list_workers(branch=registry.default_branch, schema_hash=False)
    workers_active = {worker.id for worker in workers if worker.active}

    for key, value in zip(keys, values, strict=False):
        if not key or not value:
            continue

        timestamp, worker_id = value.split("::", 1)
        if worker_id not in workers_active and Timestamp() > Timestamp(timestamp).add(
            minutes=config.SETTINGS.cache.clean_up_deadlocks_interval_mins
        ):
            await service.cache.delete(key)
            log.info(f"Deleted deadlock key={key} worker={worker_id}")


def _extract_worker_id_from_gcl(gcl_name: str) -> str | None:
    """Extract worker ID from a GCL name if it matches any per-worker GCL pattern."""
    for gcl_def in PER_WORKER_GCLS:
        match = gcl_def.get_pattern().match(gcl_name)
        if match:
            return match.group(1)
    return None


@flow(name="clean-up-stale-gcls", flow_run_name="Clean up stale global concurrency limits")
async def clean_up_stale_gcls(service: InfrahubServices) -> None:
    """Remove stale global concurrency limits left behind by inactive workers."""
    log = get_run_logger()

    workers = await service.component.list_workers(branch=registry.default_branch, schema_hash=False)
    active_worker_ids = {worker.id for worker in workers if worker.active}

    deleted_count = 0
    async with get_prefect_client(sync_client=False) as client:
        offset = 0
        limit = 100

        while True:
            gcls = await client.read_global_concurrency_limits(limit=limit, offset=offset)
            if not gcls:
                break

            deleted_count += await _delete_stale_gcls(
                client=client, gcls=gcls, active_worker_ids=active_worker_ids, log=log
            )

            if len(gcls) < limit:
                break
            offset += limit

    if deleted_count:
        log.info(f"Cleaned up {deleted_count} stale global concurrency limits")


async def _delete_stale_gcls(
    client: PrefectClient, gcls: list, active_worker_ids: set[str], log: Logger
) -> int:
    """Delete GCLs belonging to inactive workers. Returns count of deleted GCLs."""
    deleted_count = 0
    for gcl in gcls:
        worker_id = _extract_worker_id_from_gcl(gcl.name)
        if worker_id is None or worker_id in active_worker_ids:
            continue

        try:
            await client.delete_global_concurrency_limit_by_name(gcl.name)
            log.info(f"Deleted stale GCL: {gcl.name}")
            deleted_count += 1
        except Exception as exc:
            log.warning(f"Failed to delete GCL {gcl.name}: {exc}")

    return deleted_count
