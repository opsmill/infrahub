from __future__ import annotations

from prefect import flow

from infrahub.core.merge.failure_identifier import scan_for_failed_merges
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow


@flow(name="merge-watcher", flow_run_name="Detect failed merges")
async def detect_failed_merges(service: InfrahubServices) -> None:
    """Flag merges whose worker died mid-flight and keep the write-protection key in sync.

    Runs on a one-minute cron, single-flighted across workers. Each tick flips any dead merge to
    ``MERGE_FAILED`` and reconciles the shared write-protection cache key against the durable branch
    status, so the protection self-heals after a restart or cache flush.
    """
    async with service.database.start_session() as db:
        await scan_for_failed_merges(db=db, service=service)
