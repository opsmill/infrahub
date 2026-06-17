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

        cutoff = DateTime.now(tz=UTC) - timedelta(days=days_to_keep)

        flow_run_filter = FlowRunFilter(
            start_time=FlowRunFilterStartTime(before_=cutoff),
            state=FlowRunFilterState(type=FlowRunFilterStateType(any_=states)),
        )

        flow_runs = await self.client.read_flow_runs(flow_run_filter=flow_run_filter, limit=batch_size)

        deleted_total = 0

        while True:
            batch_deleted = 0
            failed_deletes = []

            for flow_run in flow_runs:
                try:
                    if delete:
                        await self.client.delete_flow_run(flow_run_id=flow_run.id)
                    else:
                        await self.client.set_flow_run_state(
                            flow_run_id=flow_run.id,
                            state=State(type=StateType.CRASHED),
                            force=True,
                        )
                    deleted_total += 1
                    batch_deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to delete flow run {flow_run.id}: {e}")
                    failed_deletes.append(flow_run.id)

                # Rate limiting
                if batch_deleted % 10 == 0:
                    await asyncio.sleep(0.5)

            logger.info(f"Delete {batch_deleted}/{len(flow_runs)} flow runs (total: {deleted_total})")

            previous_flow_run_ids = [fr.id for fr in flow_runs]
            flow_runs = await self.client.read_flow_runs(flow_run_filter=flow_run_filter, limit=batch_size)

            if not flow_runs:
                logger.info("No more flow runs to delete")
                break

            if previous_flow_run_ids == [fr.id for fr in flow_runs]:
                logger.info("Found same flow runs to delete, aborting")
                break

            # Delay between batches to avoid overwhelming the API
            await asyncio.sleep(1.0)

        logger.info(f"Retention complete. Total deleted tasks: {deleted_total}")
