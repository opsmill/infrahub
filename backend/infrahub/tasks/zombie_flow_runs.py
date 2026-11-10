from __future__ import annotations

from datetime import UTC

from prefect import flow
from prefect.client.orchestration import get_client
from prefect.logging import get_run_logger
from prefect.settings import get_current_settings
from prefect.types import DateTime

from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter
from infrahub.task_manager.flow_run.zombie import ZombieFlowRunReaper, heartbeat_window


@flow(name="crash-zombie-flow-runs", flow_run_name="Crash zombie flow runs", persist_result=False)
async def crash_zombie_flow_runs() -> None:
    """Crash flow runs whose worker died without recording a final state.

    Runs every 5 minutes. It reads the current state of each flow run and the stored heartbeats, so a delay in
    Prefect's triggers service cannot crash a run that is still alive or act on one that already finished.
    """
    window = heartbeat_window(get_current_settings().flows.heartbeat_frequency)
    async with get_client(sync_client=False) as client:
        check = await ZombieFlowRunReaper(client=PrefectClientAdapter(client), window=window).crash_zombies(
            now=DateTime.now(tz=UTC)
        )
    log = get_run_logger()
    if not check.events_stored:
        log.warning(f"Judged no flow run: no event was stored in the last {window.total_seconds():.0f} seconds")
    if check.crashed:
        log.info(f"Crashed {len(check.crashed)} zombie flow runs: {check.crashed}")
