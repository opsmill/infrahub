from __future__ import annotations

from datetime import UTC

from prefect import flow
from prefect.client.orchestration import get_client
from prefect.logging import get_run_logger
from prefect.types import DateTime

from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter
from infrahub.task_manager.flow_run.zombie import ZombieFlowRunReaper


@flow(name="crash-zombie-flow-runs", flow_run_name="Crash zombie flow runs", persist_result=False)
async def crash_zombie_flow_runs() -> None:
    """Crash flow runs whose worker died without recording a final state.

    Runs on a one-minute cron, single-flighted across workers. It reads the current state of each
    running flow run, so a delay in processing events cannot crash a run that is still alive or act
    on one that already finished.
    """
    async with get_client(sync_client=False) as client:
        crashed = await ZombieFlowRunReaper(client=PrefectClientAdapter(client)).crash_zombies(now=DateTime.now(tz=UTC))
    if crashed:
        get_run_logger().info(f"Crashed {len(crashed)} flow runs that stopped sending heartbeats: {crashed}")
