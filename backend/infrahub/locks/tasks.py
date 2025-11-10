from __future__ import annotations

from prefect import flow
from prefect.logging import get_run_logger

from infrahub import config
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.lock import LOCK_PREFIX
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow


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
