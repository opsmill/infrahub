import asyncio
from datetime import UTC

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.responses import DeploymentResponse
from prefect.client.schemas.schedules import CronSchedule
from prefect.types import DateTime

from infrahub.message_bus.types import KVTTL
from infrahub.services.adapters.cache import InfrahubCache
from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter
from infrahub.task_manager.flow_run.tags import WorkflowTagDecoder
from infrahub.workers.dependencies import get_cache
from infrahub.workflows.catalogue import WORKFLOWS

from .health import assess_health
from .models import ScheduledFlowHealth, ScheduledFlowQueryResult, ScheduledFlowSummary
from .reader import ScheduledFlowReader, ScheduledFlowReaderProtocol
from .schedule_window import interval_seconds, next_fire_times

CACHE_KEY = "task_manager:scheduled_flows"

# Where a flow appears in the list once it has a verdict. This is not the order in which verdicts are
# assigned: paused sits near the bottom because a switched-off schedule needs no attention.
HEALTH_ORDER = {
    ScheduledFlowHealth.OVERDUE: 0,
    ScheduledFlowHealth.FAILED: 1,
    ScheduledFlowHealth.CANCELLED: 2,
    ScheduledFlowHealth.NO_RECENT_RUNS: 3,
    ScheduledFlowHealth.NEVER_RUN: 4,
    ScheduledFlowHealth.PAUSED: 5,
    ScheduledFlowHealth.HEALTHY: 6,
}


class ScheduledFlowService:
    """Assemble one summary per scheduled deployment, ordered so the flows needing attention come first."""

    def __init__(
        self,
        reader: ScheduledFlowReaderProtocol,
        tag_decoder: WorkflowTagDecoder,
        cache: InfrahubCache,
        catalogue_crons: dict[str, str],
    ) -> None:
        self.reader = reader
        self.tag_decoder = tag_decoder
        self.cache = cache
        self.catalogue_crons = catalogue_crons

    async def query(self) -> ScheduledFlowQueryResult:
        cached = await self.cache.get(key=CACHE_KEY)
        if cached is not None:
            return ScheduledFlowQueryResult.model_validate_json(cached)

        result = await self._assemble()
        await self.cache.set(key=CACHE_KEY, value=result.model_dump_json(), expires=KVTTL.ONE_MINUTE)
        return result

    async def _assemble(self) -> ScheduledFlowQueryResult:
        now = DateTime.now(tz=UTC)
        deployments = await self.reader.read_deployments()
        scheduled = [
            (deployment, schedule) for deployment in deployments for schedule in self._cron_schedules(deployment)
        ]

        summaries = await asyncio.gather(
            *(self._summarise(deployment=deployment, schedule=schedule, now=now) for deployment, schedule in scheduled)
        )
        summaries.sort(key=lambda summary: (HEALTH_ORDER[summary.health], summary.name))

        registered = {deployment.name for deployment, _ in scheduled}
        catalogue_only = sorted(name for name in self.catalogue_crons if name not in registered)

        return ScheduledFlowQueryResult(flows=summaries, catalogue_only=catalogue_only)

    async def _summarise(
        self, deployment: DeploymentResponse, schedule: tuple[CronSchedule, bool], now: DateTime
    ) -> ScheduledFlowSummary:
        cron_schedule, schedule_active = schedule
        active = schedule_active and not deployment.paused

        interval, fire_times, latest_run, recent_outcomes = await asyncio.gather(
            interval_seconds(cron=cron_schedule.cron, start=now, timezone=cron_schedule.timezone),
            next_fire_times(cron=cron_schedule.cron, start=now, count=1, timezone=cron_schedule.timezone),
            self.reader.read_latest_executed_run(deployment_id=deployment.id, now=now),
            self.reader.read_recent_outcomes(deployment_id=deployment.id, now=now),
        )

        return ScheduledFlowSummary(
            deployment_id=deployment.id,
            name=deployment.name,
            workflow_type=self.tag_decoder.workflow_type_from_tags(tags=deployment.tags),
            cron=cron_schedule.cron,
            timezone=cron_schedule.timezone,
            interval_seconds=interval,
            next_run_at=fire_times[0] if fire_times else None,
            active=active,
            # DeploymentResponse.concurrency_limit is deprecated and always None; the live value
            # lives on the global concurrency limit object.
            concurrency_limit=(
                deployment.global_concurrency_limit.limit if deployment.global_concurrency_limit else None
            ),
            collision_strategy=(
                deployment.concurrency_options.collision_strategy if deployment.concurrency_options else None
            ),
            latest_run=latest_run,
            recent_outcomes=recent_outcomes,
            health=assess_health(
                latest_run=latest_run,
                interval_seconds=interval,
                active=active,
                deployment_created_at=deployment.created,
                now=now,
            ),
            deployment_created_at=deployment.created,
        )

    @staticmethod
    def _cron_schedules(deployment: DeploymentResponse) -> list[tuple[CronSchedule, bool]]:
        return [
            (entry.schedule, entry.active) for entry in deployment.schedules if isinstance(entry.schedule, CronSchedule)
        ]


async def build_scheduled_flow_service(client: PrefectClient) -> ScheduledFlowService:
    cache = await get_cache()
    return ScheduledFlowService(
        reader=ScheduledFlowReader(client=PrefectClientAdapter(client)),
        tag_decoder=WorkflowTagDecoder(),
        cache=cache,
        catalogue_crons={workflow.name: workflow.cron for workflow in WORKFLOWS if workflow.cron},
    )
