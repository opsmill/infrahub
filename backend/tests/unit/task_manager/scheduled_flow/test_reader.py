from datetime import timedelta

import pytest
from prefect.client.schemas.objects import StateType
from prefect.client.schemas.sorting import FlowRunSort
from prefect.types import DateTime

from infrahub.task_manager.scheduled_flow.reader import (
    DEPLOYMENT_PAGE_SIZE,
    RECENT_OUTCOME_WINDOW_HOURS,
    ScheduledFlowReader,
)

from .doubles import NOW, DeploymentSpec, FlowRunSpec, RecordingScheduledFlowClient, make_deployment, make_flow_run


class TestReadDeployments:
    async def test_a_single_short_page_is_read_once(self) -> None:
        client = RecordingScheduledFlowClient(
            deployments=[make_deployment(DeploymentSpec(name=f"flow-{index}")) for index in range(3)]
        )

        deployments = await ScheduledFlowReader(client=client).read_deployments()

        assert [deployment.name for deployment in deployments] == ["flow-0", "flow-1", "flow-2"]
        assert client.deployment_reads == [(DEPLOYMENT_PAGE_SIZE, 0)]

    async def test_every_page_is_walked_so_no_deployment_is_silently_dropped(self) -> None:
        total = DEPLOYMENT_PAGE_SIZE + 5
        client = RecordingScheduledFlowClient(
            deployments=[make_deployment(DeploymentSpec(name=f"flow-{index:03d}")) for index in range(total)]
        )

        deployments = await ScheduledFlowReader(client=client).read_deployments()

        assert len(deployments) == total
        assert client.deployment_reads == [(DEPLOYMENT_PAGE_SIZE, 0), (DEPLOYMENT_PAGE_SIZE, DEPLOYMENT_PAGE_SIZE)]

    async def test_a_full_last_page_still_terminates(self) -> None:
        client = RecordingScheduledFlowClient(
            deployments=[
                make_deployment(DeploymentSpec(name=f"flow-{index:03d}")) for index in range(DEPLOYMENT_PAGE_SIZE)
            ]
        )

        deployments = await ScheduledFlowReader(client=client).read_deployments()

        assert len(deployments) == DEPLOYMENT_PAGE_SIZE
        assert client.deployment_reads == [(DEPLOYMENT_PAGE_SIZE, 0), (DEPLOYMENT_PAGE_SIZE, DEPLOYMENT_PAGE_SIZE)]


class TestReadLatestExecutedRun:
    @staticmethod
    def _filter_of(client: RecordingScheduledFlowClient) -> tuple[list[StateType], DateTime, int | None, FlowRunSort]:
        flow_run_filter, limit, sort = client.flow_run_reads[0]
        assert flow_run_filter is not None
        assert flow_run_filter.state is not None
        assert flow_run_filter.state.type is not None
        assert flow_run_filter.state.type.not_any_ is not None
        assert flow_run_filter.expected_start_time is not None
        assert flow_run_filter.expected_start_time.before_ is not None
        assert sort is not None
        return (
            flow_run_filter.state.type.not_any_,
            flow_run_filter.expected_start_time.before_,
            limit,
            sort,
        )

    async def test_a_run_that_has_not_executed_yet_is_excluded_and_only_one_run_is_read(self) -> None:
        deployment = make_deployment(DeploymentSpec(name="git_repositories_sync"))
        client = RecordingScheduledFlowClient(
            flow_runs=[
                make_flow_run(
                    FlowRunSpec(state_type=StateType.COMPLETED, expected_start_time=NOW - timedelta(seconds=30))
                ),
            ]
        )

        latest = await ScheduledFlowReader(client=client).read_latest_executed_run(deployment_id=deployment.id, now=NOW)

        assert latest is not None
        assert latest.state_type == StateType.COMPLETED
        excluded_states, before, limit, sort = self._filter_of(client)
        # Prefect pre-creates roughly an hour of future runs per schedule with no worker alive, so a
        # stalled flow would read as healthy if either bound were dropped.
        assert excluded_states == [StateType.SCHEDULED, StateType.PENDING]
        assert before == NOW
        assert limit == 1
        # Sorting on start_time would hide a run cancelled before it ever began.
        assert sort == FlowRunSort.EXPECTED_START_TIME_DESC

    async def test_the_deployment_is_the_only_one_selected(self) -> None:
        deployment = make_deployment(DeploymentSpec(name="clean-up-deadlocks"))
        client = RecordingScheduledFlowClient()

        await ScheduledFlowReader(client=client).read_latest_executed_run(deployment_id=deployment.id, now=NOW)

        flow_run_filter, _, _ = client.flow_run_reads[0]
        assert flow_run_filter is not None
        assert flow_run_filter.deployment_id is not None
        assert flow_run_filter.deployment_id.any_ == [deployment.id]

    async def test_every_field_of_the_run_is_carried_through(self) -> None:
        """The list renders the outcome and both timestamps, so dropping one blanks a column."""
        spec = FlowRunSpec(
            state_type=StateType.CANCELLED,
            expected_start_time=NOW - timedelta(minutes=5),
            state_name="Cancelled",
            start_time=NOW - timedelta(minutes=4),
            end_time=NOW - timedelta(minutes=3),
        )
        run = make_flow_run(spec)
        client = RecordingScheduledFlowClient(flow_runs=[run])

        latest = await ScheduledFlowReader(client=client).read_latest_executed_run(
            deployment_id=make_deployment(DeploymentSpec(name="git_repositories_sync")).id, now=NOW
        )

        assert latest is not None
        assert latest.id == run.id
        assert latest.state_type == StateType.CANCELLED
        assert latest.state_name == "Cancelled"
        assert latest.expected_start_time == spec.expected_start_time
        assert latest.start_time == spec.start_time
        assert latest.end_time == spec.end_time

    async def test_no_run_at_all_reports_none(self) -> None:
        client = RecordingScheduledFlowClient()

        latest = await ScheduledFlowReader(client=client).read_latest_executed_run(
            deployment_id=make_deployment(DeploymentSpec(name="never-run")).id, now=NOW
        )

        assert latest is None


class TestReadRecentOutcomes:
    async def test_the_window_is_one_bucket_aggregated_by_prefect(self) -> None:
        deployment = make_deployment(DeploymentSpec(name="git_repositories_sync"))
        client = RecordingScheduledFlowClient(
            history=[{"states": [{"state_type": "COMPLETED", "count_runs": 1430}]}],
        )

        outcomes = await ScheduledFlowReader(client=client).read_recent_outcomes(deployment_id=deployment.id, now=NOW)

        assert outcomes.counts == {StateType.COMPLETED: 1430}
        assert outcomes.window_hours == RECENT_OUTCOME_WINDOW_HOURS
        window_seconds = timedelta(hours=RECENT_OUTCOME_WINDOW_HOURS).total_seconds()
        assert client.history_reads == [
            {
                "history_start": (NOW - timedelta(hours=RECENT_OUTCOME_WINDOW_HOURS)).isoformat(),
                "history_end": NOW.isoformat(),
                "history_interval_seconds": window_seconds,
                "deployments": {"id": {"any_": [str(deployment.id)]}},
            }
        ]
        # The 1440 runs behind that count are never listed.
        assert client.flow_run_reads == []

    async def test_counts_from_several_buckets_are_summed_per_state(self) -> None:
        client = RecordingScheduledFlowClient(
            history=[
                {"states": [{"state_type": "COMPLETED", "count_runs": 10}, {"state_type": "FAILED", "count_runs": 2}]},
                {"states": [{"state_type": "COMPLETED", "count_runs": 5}]},
            ],
        )

        outcomes = await ScheduledFlowReader(client=client).read_recent_outcomes(
            deployment_id=make_deployment(DeploymentSpec(name="a-flow")).id, now=NOW
        )

        assert outcomes.counts == {StateType.COMPLETED: 15, StateType.FAILED: 2}
        assert outcomes.total == 17

    async def test_a_state_prefect_adds_later_is_ignored_rather_than_crashing_the_view(self) -> None:
        client = RecordingScheduledFlowClient(
            history=[
                {
                    "states": [
                        {"state_type": "SOMETHING_NEW", "count_runs": 3},
                        {"state_type": "CANCELLED", "count_runs": 1},
                    ]
                }
            ],
        )

        outcomes = await ScheduledFlowReader(client=client).read_recent_outcomes(
            deployment_id=make_deployment(DeploymentSpec(name="a-flow")).id, now=NOW
        )

        assert outcomes.counts == {StateType.CANCELLED: 1}

    async def test_prefect_failures_propagate(self) -> None:
        class FailingClient(RecordingScheduledFlowClient):
            async def flow_run_history(self, body: dict[str, object]) -> list[dict[str, object]]:
                raise ConnectionError("Prefect is unreachable")

        with pytest.raises(ConnectionError, match=r"^Prefect is unreachable$"):
            await ScheduledFlowReader(client=FailingClient()).read_recent_outcomes(
                deployment_id=make_deployment(DeploymentSpec(name="a-flow")).id, now=NOW
            )
