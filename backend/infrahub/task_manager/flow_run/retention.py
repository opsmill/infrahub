import asyncio
from datetime import UTC, timedelta

from prefect import State
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterStartTime,
    FlowRunFilterState,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import StateType
from prefect.types import DateTime

from infrahub.log import get_logger

from .prefect_client import RetentionPrefectClient


class FlowRunRetention:
    """Purge old flow runs, either deleting them or forcing them into a terminal state."""

    def __init__(self, client: RetentionPrefectClient) -> None:
        self.client = client

    async def purge(
        self,
        states: list[StateType] | None = None,
        delete: bool = True,
        days_to_keep: int = 2,
        batch_size: int = 100,
    ) -> None:
        states = states or [StateType.COMPLETED, StateType.FAILED, StateType.CANCELLED]
        logger = get_logger()
        action = "delete" if delete else "mark as crashed"

        cutoff = DateTime.now(tz=UTC) - timedelta(days=days_to_keep)

        flow_run_filter = FlowRunFilter(
            start_time=FlowRunFilterStartTime(before_=cutoff),
            state=FlowRunFilterState(type=FlowRunFilterStateType(any_=states)),
        )

        flow_runs = await self.client.read_flow_runs(flow_run_filter=flow_run_filter, limit=batch_size)

        purged_total = 0

        while True:
            batch_purged = 0
            failed_purges = []

            for index, flow_run in enumerate(flow_runs, start=1):
                try:
                    if delete:
                        await self.client.delete_flow_run(flow_run_id=flow_run.id)
                    else:
                        await self.client.set_flow_run_state(
                            flow_run_id=flow_run.id,
                            state=State(type=StateType.CRASHED),
                            force=True,
                        )
                    purged_total += 1
                    batch_purged += 1
                except Exception as e:
                    logger.warning(f"Failed to {action} flow run {flow_run.id}: {e}")
                    failed_purges.append(flow_run.id)

                # Rate limiting, based on runs processed so failures throttle the same way as successes.
                if index % 10 == 0:
                    await asyncio.sleep(0.5)

            logger.info(f"Purged ({action}) {batch_purged}/{len(flow_runs)} flow runs (total: {purged_total})")

            previous_flow_run_ids = [fr.id for fr in flow_runs]
            flow_runs = await self.client.read_flow_runs(flow_run_filter=flow_run_filter, limit=batch_size)

            if not flow_runs:
                logger.info("No more flow runs to purge")
                break

            if previous_flow_run_ids == [fr.id for fr in flow_runs]:
                logger.info("Found same flow runs to purge, aborting")
                break

            # Delay between batches to avoid overwhelming the API
            await asyncio.sleep(1.0)

        logger.info(f"Retention complete. Total purged tasks: {purged_total}")
