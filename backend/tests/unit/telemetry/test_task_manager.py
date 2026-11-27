import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import StateType

from infrahub.telemetry.constants import WorkflowRunState
from infrahub.telemetry.models import TelemetryWorkflowRunData
from infrahub.telemetry.task_manager import (
    RunHistoryState,
    build_workflow_run_rows,
    count_started_validators,
    gather_workflow_runs,
    read_within_deadline,
)

WORKFLOW = "generator-run"
WINDOW_START = datetime(2021, 3, 1, tzinfo=UTC)
WINDOW_END = datetime(2021, 3, 2, tzinfo=UTC)
# Long enough that no scripted answer reaches it.
READ_DEADLINE_SECONDS = 30.0


def _state(state_type: StateType, runs: int, seconds: float) -> RunHistoryState:
    return RunHistoryState(state_type=state_type, count_runs=runs, sum_estimated_run_time=timedelta(seconds=seconds))


def _row(state: str, runs: int, run_seconds: int) -> TelemetryWorkflowRunData:
    return TelemetryWorkflowRunData(
        workflow=WORKFLOW, state=WorkflowRunState(state), runs=runs, run_seconds=run_seconds
    )


@dataclass
class RunRowsCase:
    name: str
    states: list[RunHistoryState]
    expected: list[TelemetryWorkflowRunData]


RUN_ROWS_CASES: list[RunRowsCase] = [
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


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in RUN_ROWS_CASES])
def test_build_workflow_run_rows(case: RunRowsCase) -> None:
    assert build_workflow_run_rows(workflow=WORKFLOW, states=case.states) == case.expected


def _task_manager_client(
    answer: Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]],
) -> PrefectClient:
    """Return a task manager client whose requests are answered by ``answer`` instead of a server."""

    async def handle(request: httpx.Request) -> httpx.Response:
        # The client asks for a CSRF token before its first write; 404 tells it the server has none.
        if request.url.path.endswith("/csrf-token"):
            return httpx.Response(status_code=404)
        response = answer(request)
        if isinstance(response, httpx.Response):
            return response
        return await response

    return PrefectClient(
        api="http://task-manager.invalid/api", httpx_settings={"transport": httpx.MockTransport(handle)}
    )


def _answer_run_history(request: httpx.Request) -> httpx.Response:
    """Fail the history of ``generator-run``, return two completed runs for ``artifact-generate`` and none for the rest."""
    workflow = json.loads(request.content)["flows"]["name"]["any_"][0]
    if workflow == "generator-run":
        # The client tries again after 408, 429, 502 and 503, so the failure is a status it gives up on.
        return httpx.Response(status_code=500)
    states = []
    if workflow == "artifact-generate":
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


async def test_gather_workflow_runs_keeps_the_other_rows_when_one_read_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="infrahub.tasks"):
        async with _task_manager_client(answer=_answer_run_history) as client:
            rows = await gather_workflow_runs(
                client=client,
                window_start=WINDOW_START,
                window_end=WINDOW_END,
                read_deadline_seconds=READ_DEADLINE_SECONDS,
            )

    assert rows == [
        TelemetryWorkflowRunData(workflow="generator-run"),
        TelemetryWorkflowRunData(workflow="artifact-generate", state=WorkflowRunState.COMPLETED, runs=2, run_seconds=3),
    ]
    # The log line names the workflow whose read failed and the type of the failure.
    assert [record.getMessage().split(" for url ")[0] for record in caplog.records] == [
        "Telemetry metric activity_24h.workflow_runs.generator-run could not be read; reporting null: "
        "PrefectHTTPStatusError: Server error '500 Internal Server Error'"
    ]


async def _never_answers_generator_run(request: httpx.Request) -> httpx.Response:
    """Leave the history of ``generator-run`` unanswered and return no run for the other workflows."""
    workflow = json.loads(request.content)["flows"]["name"]["any_"][0]
    if workflow == "generator-run":
        await asyncio.Event().wait()
    return httpx.Response(status_code=200, json=[{"states": []}])


async def test_gather_workflow_runs_gives_up_a_read_that_is_not_answered_within_the_deadline(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="infrahub.tasks"):
        async with _task_manager_client(answer=_never_answers_generator_run) as client:
            rows = await gather_workflow_runs(
                client=client, window_start=WINDOW_START, window_end=WINDOW_END, read_deadline_seconds=0.05
            )

    assert rows == [TelemetryWorkflowRunData(workflow="generator-run")]
    assert [record.getMessage() for record in caplog.records] == [
        "Telemetry metric activity_24h.workflow_runs.generator-run could not be read; reporting null: "
        "TimeoutError: The task manager did not answer within 0.05 seconds"
    ]


async def test_read_within_deadline_keeps_a_timeout_that_the_read_raises() -> None:
    async def read() -> int:
        raise TimeoutError("raised by the read")

    with pytest.raises(TimeoutError, match="raised by the read"):
        await read_within_deadline(read(), deadline_seconds=READ_DEADLINE_SECONDS)


async def test_count_started_validators_keeps_the_other_kinds_when_one_count_fails() -> None:
    def read_kinds() -> list[str]:
        return ["CoreUserValidator", "CoreDataValidator"]

    async with _task_manager_client(answer=_answer_validator_count) as client:
        counts = await count_started_validators(
            client=client,
            read_kinds=read_kinds,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            read_deadline_seconds=READ_DEADLINE_SECONDS,
        )

    assert counts == {"CoreUserValidator": None, "CoreDataValidator": 3}


def _answer_validator_count_with_unexpected_shapes(request: httpx.Request) -> httpx.Response:
    """Answer 200 for every kind: a body that is not a list, a bucket with no count, and three events."""
    kind = json.loads(request.content)["filter"]["resource"]["labels"]["infrahub.node.kind"][0]
    if kind == "CoreSchemaValidator":
        return httpx.Response(status_code=200, json={"detail": "not a list of buckets"})
    if kind == "CoreUserValidator":
        return httpx.Response(status_code=200, json=[{"label": "a bucket with no count"}])
    return httpx.Response(status_code=200, json=[{"count": 3}])


async def test_count_started_validators_reports_null_for_a_response_with_an_unexpected_shape() -> None:
    def read_kinds() -> list[str]:
        return ["CoreSchemaValidator", "CoreUserValidator", "CoreDataValidator"]

    async with _task_manager_client(answer=_answer_validator_count_with_unexpected_shapes) as client:
        counts = await count_started_validators(
            client=client,
            read_kinds=read_kinds,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            read_deadline_seconds=READ_DEADLINE_SECONDS,
        )

    assert counts == {"CoreSchemaValidator": None, "CoreUserValidator": None, "CoreDataValidator": 3}
