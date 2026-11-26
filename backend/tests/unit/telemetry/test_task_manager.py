import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import StateType

from infrahub.telemetry.models import TelemetryWorkflowRunData
from infrahub.telemetry.task_manager import (
    RunHistoryState,
    build_workflow_run_rows,
    count_started_validators,
    gather_workflow_runs,
)

WORKFLOW = "generator-run"
WINDOW_START = datetime(2021, 3, 1, tzinfo=UTC)
WINDOW_END = datetime(2021, 3, 2, tzinfo=UTC)


def _state(state_type: StateType, runs: int, seconds: float) -> RunHistoryState:
    return RunHistoryState(state_type=state_type, count_runs=runs, sum_estimated_run_time=timedelta(seconds=seconds))


def _row(state: str, runs: int, run_seconds: int) -> TelemetryWorkflowRunData:
    return TelemetryWorkflowRunData(workflow=WORKFLOW, state=state, runs=runs, run_seconds=run_seconds)


@dataclass
class RunRowsCase:
    name: str
    states: list[RunHistoryState]
    expected: list[TelemetryWorkflowRunData]


RUN_ROWS_CASES = [
    RunRowsCase(name="no_run_gives_no_row", states=[], expected=[]),
    RunRowsCase(
        # Rounding each entry first would give 2 seconds.
        name="entries_of_one_state_type_are_added_up_before_rounding",
        states=[
            _state(state_type=StateType.FAILED, runs=2, seconds=1.4),
            _state(state_type=StateType.FAILED, runs=1, seconds=1.4),
        ],
        expected=[_row(state="FAILED", runs=3, run_seconds=3)],
    ),
    RunRowsCase(
        name="states_that_are_not_end_states_are_left_out",
        states=[
            _state(state_type=StateType.RUNNING, runs=4, seconds=90.0),
            _state(state_type=StateType.SCHEDULED, runs=2, seconds=0.0),
            _state(state_type=StateType.COMPLETED, runs=5, seconds=12.2),
        ],
        expected=[_row(state="COMPLETED", runs=5, run_seconds=12)],
    ),
    RunRowsCase(
        name="rows_follow_the_reported_state_order",
        states=[
            _state(state_type=StateType.CANCELLED, runs=1, seconds=0.0),
            _state(state_type=StateType.CRASHED, runs=2, seconds=7.6),
            _state(state_type=StateType.FAILED, runs=3, seconds=30.0),
            _state(state_type=StateType.COMPLETED, runs=4, seconds=120.0),
        ],
        expected=[
            _row(state="COMPLETED", runs=4, run_seconds=120),
            _row(state="FAILED", runs=3, run_seconds=30),
            _row(state="CRASHED", runs=2, run_seconds=8),
            _row(state="CANCELLED", runs=1, run_seconds=0),
        ],
    ),
]


@pytest.mark.parametrize("case", RUN_ROWS_CASES, ids=[case.name for case in RUN_ROWS_CASES])
def test_build_workflow_run_rows(case: RunRowsCase) -> None:
    assert build_workflow_run_rows(workflow=WORKFLOW, states=case.states) == case.expected


def _task_manager_client(answer: Callable[[httpx.Request], httpx.Response]) -> PrefectClient:
    """Return a task manager client whose requests are answered by ``answer`` instead of a server."""

    def handle(request: httpx.Request) -> httpx.Response:
        # The client asks for a CSRF token before its first write; 404 tells it the server has none.
        if request.url.path.endswith("/csrf-token"):
            return httpx.Response(status_code=404)
        return answer(request)

    return PrefectClient(
        api="http://task-manager.invalid/api", httpx_settings={"transport": httpx.MockTransport(handle)}
    )


def _answer_run_history(request: httpx.Request) -> httpx.Response:
    """Fail the history of ``artifact-generate``, return two completed runs for ``generator-run`` and none for the rest."""
    workflow = json.loads(request.content)["flows"]["name"]["any_"][0]
    if workflow == "artifact-generate":
        # The client tries again after 408, 429, 502 and 503, so the failure is a status it gives up on.
        return httpx.Response(status_code=500)
    states = []
    if workflow == "generator-run":
        states = [
            {"state_type": "COMPLETED", "state_name": "Completed", "count_runs": 2, "sum_estimated_run_time": 3.2}
        ]
    return httpx.Response(status_code=200, json=[{"states": states}])


def _answer_validator_count(request: httpx.Request) -> httpx.Response:
    """Fail the count of ``CoreUserValidator`` and return three events for any other kind."""
    kind = json.loads(request.content)["filter"]["resource"]["labels"]["infrahub.node.kind"][0]
    if kind == "CoreUserValidator":
        return httpx.Response(status_code=500)
    return httpx.Response(status_code=200, json=[{"count": 3}])


async def test_gather_workflow_runs_keeps_the_other_rows_when_one_read_fails() -> None:
    async with _task_manager_client(answer=_answer_run_history) as client:
        rows = await gather_workflow_runs(client=client, window_start=WINDOW_START, window_end=WINDOW_END)

    assert rows == [
        TelemetryWorkflowRunData(workflow="generator-run", state="COMPLETED", runs=2, run_seconds=3),
        TelemetryWorkflowRunData(workflow="artifact-generate"),
    ]


async def test_count_started_validators_keeps_the_other_kinds_when_one_count_fails() -> None:
    def read_kinds() -> list[str]:
        return ["CoreDataValidator", "CoreUserValidator"]

    async with _task_manager_client(answer=_answer_validator_count) as client:
        counts = await count_started_validators(
            client=client, read_kinds=read_kinds, window_start=WINDOW_START, window_end=WINDOW_END
        )

    assert counts == {"CoreDataValidator": 3, "CoreUserValidator": None}
