from __future__ import annotations

import json
import re
import subprocess  # noqa: S404 - only a fresh interpreter shows what an import loads
import sys
from dataclasses import dataclass
from datetime import date, timedelta

import httpx
import pytest

from infrahub.prefect_server.task_history_models import CleanupJob, CleanupJobState, CleanupRewrite
from infrahub.task_manager.flow_run.cleanup import (
    CleanupWait,
    TaskHistoryCleanupError,
    TaskHistoryCleanupFailedError,
    run_task_history_cleanup,
)
from tests.helpers.task_history_api import (
    CLEANUP_PATH,
    FakeClock,
    RecordedRequest,
    ScriptedTaskManager,
    polled,
    route_missing,
    running_elsewhere,
    started,
    unknown_cleanup,
    unreachable,
)

POLL_INTERVAL = timedelta(seconds=2)


class RecordedReports:
    """The progress and the waits the client reported, each in order."""

    def __init__(self) -> None:
        self.progress: list[tuple[str, date | None, int]] = []
        self.waits: list[CleanupWait] = []

    def on_progress(self, job: CleanupJob) -> None:
        self.progress.append((job.id, job.current_day, job.deleted_runs))

    def on_wait(self, wait: CleanupWait) -> None:
        self.waits.append(wait)


async def _run(
    task_manager: ScriptedTaskManager,
    clock: FakeClock,
    reports: RecordedReports | None = None,
    rewrite: CleanupRewrite = CleanupRewrite.NEVER,
    give_up_after: timedelta = timedelta(hours=1),
) -> CleanupJob | None:
    reports = reports or RecordedReports()
    async with task_manager.client() as client:
        return await run_task_history_cleanup(
            client=client,
            rewrite=rewrite,
            on_progress=reports.on_progress,
            on_wait=reports.on_wait,
            poll_interval=POLL_INTERVAL,
            give_up_after=give_up_after,
            clock=clock,
            sleep=clock.sleep,
        )


def test_importing_the_client_loads_neither_the_task_manager_database_nor_its_driver() -> None:
    """The client imports without Prefect's server database layer or the Postgres driver the task manager uses."""
    probe = (
        "import json, sys; import infrahub.task_manager.flow_run.cleanup; "
        "print(json.dumps({name: name in sys.modules for name in ('asyncpg', 'prefect.server.database')}))"
    )

    result = subprocess.run(args=[sys.executable, "-c", probe], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"asyncpg": False, "prefect.server.database": False}


async def test_a_task_manager_without_the_cleanup_route_runs_no_cleanup() -> None:
    """A task manager that answers 404 to the start of a cleanup provides no cleanup, and nothing is retried."""
    task_manager = ScriptedTaskManager(responses=[route_missing()])
    clock = FakeClock()

    result = await _run(task_manager=task_manager, clock=clock, rewrite=CleanupRewrite.ALWAYS)

    assert result is None
    assert task_manager.requests == [RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "always"})]
    assert clock.sleeps == []


async def test_a_cleanup_is_polled_until_it_completes_reporting_each_change_of_progress() -> None:
    """The cleanup is read after each wait until it completes, and progress is reported only when it changes."""
    task_manager = ScriptedTaskManager(
        responses=[
            started(rewrite="if_freed"),
            polled(rewrite="if_freed", current_day="2026-01-15", deleted_runs=5),
            polled(rewrite="if_freed", current_day="2026-01-15", deleted_runs=5),
            polled(rewrite="if_freed", current_day="2026-01-16", deleted_runs=9),
            polled(
                rewrite="if_freed",
                state="completed",
                rewritten=True,
                current_day="2026-01-17",
                deleted_runs=12,
                size_before=1000,
                size_after=100,
            ),
        ]
    )
    clock = FakeClock()
    reports = RecordedReports()

    result = await _run(task_manager=task_manager, clock=clock, reports=reports, rewrite=CleanupRewrite.IF_FREED)

    assert result is not None
    assert (result.state, result.rewritten, result.deleted_runs, result.size_before, result.size_after) == (
        CleanupJobState.COMPLETED,
        True,
        12,
        1000,
        100,
    )
    assert task_manager.requests == [
        RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "if_freed"}),
        *[RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-1")] * 4,
    ]
    assert reports.progress == [("job-1", date(2026, 1, 15), 5), ("job-1", date(2026, 1, 16), 9)]
    assert clock.sleeps == [2.0, 2.0, 2.0, 2.0]


async def test_a_cleanup_running_elsewhere_is_started_again_after_a_wait() -> None:
    """While another task manager runs a cleanup, the start is posted again after each wait."""
    task_manager = ScriptedTaskManager(
        responses=[running_elsewhere(), running_elsewhere(), started(), polled(state="completed", deleted_runs=3)]
    )
    clock = FakeClock()

    result = await _run(task_manager=task_manager, clock=clock)

    assert result is not None
    assert (result.state, result.deleted_runs) == (CleanupJobState.COMPLETED, 3)
    assert task_manager.requests == [
        *[RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "never"})] * 3,
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-1"),
    ]
    assert clock.sleeps == [2.0, 2.0, 2.0]


async def test_a_cleanup_the_task_manager_no_longer_knows_is_started_again_after_a_wait() -> None:
    """A cleanup the task manager answers 404 about while it is polled is started again, as a new cleanup."""
    task_manager = ScriptedTaskManager(
        responses=[
            started(),
            polled(current_day="2026-01-15", deleted_runs=4),
            unknown_cleanup(),
            started(id="job-2"),
            polled(id="job-2", current_day="2026-01-16", deleted_runs=2),
            polled(id="job-2", state="completed", current_day="2026-01-16", deleted_runs=2),
        ]
    )
    clock = FakeClock()
    reports = RecordedReports()

    result = await _run(task_manager=task_manager, clock=clock, reports=reports)

    assert result is not None
    assert (result.id, result.state, result.deleted_runs) == ("job-2", CleanupJobState.COMPLETED, 2)
    assert task_manager.requests == [
        RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "never"}),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-1"),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-1"),
        RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "never"}),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-2"),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-2"),
    ]
    assert reports.progress == [("job-1", date(2026, 1, 15), 4), ("job-2", date(2026, 1, 16), 2)]
    assert clock.sleeps == [2.0] * 5


async def test_a_failed_cleanup_raises_the_error_the_task_manager_recorded_with_the_job() -> None:
    """A cleanup that ends failed raises with the error the task manager recorded on it, holding the job as it ended."""
    task_manager = ScriptedTaskManager(
        responses=[
            started(rewrite="always"),
            polled(
                rewrite="always",
                state="failed",
                rewritten=True,
                current_day="2026-01-15",
                deleted_runs=7,
                not_rewritten=["log"],
                error="The cleanup failed with DBAPIError; the task manager log has the details",
            ),
        ]
    )

    with pytest.raises(
        TaskHistoryCleanupFailedError,
        match=r"^The cleanup failed with DBAPIError; the task manager log has the details$",
    ) as raised:
        await _run(task_manager=task_manager, clock=FakeClock(), rewrite=CleanupRewrite.ALWAYS)

    job = raised.value.job
    assert (job.id, job.state, job.deleted_runs, job.current_day, job.rewritten, job.not_rewritten) == (
        "job-1",
        CleanupJobState.FAILED,
        7,
        date(2026, 1, 15),
        True,
        ["log"],
    )


async def test_waiting_for_a_cleanup_gives_up_when_the_task_manager_never_shows_one() -> None:
    """The start is posted again until the task manager has shown no cleanup for the wait limit, then it gives up."""
    task_manager = ScriptedTaskManager(responses=[running_elsewhere() for _ in range(6)])
    clock = FakeClock()
    reports = RecordedReports()

    with pytest.raises(
        TaskHistoryCleanupError,
        match=(
            r"^Gave up after 10 seconds without a cleanup to follow, "
            r"when the task manager answered that a cleanup runs elsewhere$"
        ),
    ):
        await _run(task_manager=task_manager, clock=clock, reports=reports, give_up_after=timedelta(seconds=10))

    assert len(task_manager.requests) == 6
    assert clock.sleeps == [2.0] * 5
    assert reports.waits == [CleanupWait.RUNNING_ELSEWHERE]


@pytest.mark.usefixtures("prefect_client_without_retries")
async def test_a_wait_is_reported_when_it_starts_when_its_reason_changes_and_again_after_a_cleanup_shows() -> None:
    """A wait is reported once while its reason holds, again when the reason changes, and again after a cleanup showed."""
    task_manager = ScriptedTaskManager(
        responses=[
            running_elsewhere(),
            running_elsewhere(),
            started(),
            unknown_cleanup(),
            started(id="job-2"),
            unknown_cleanup(),
            running_elsewhere(),
            started(id="job-3"),
            unreachable(),
            unreachable(),
            started(id="job-4"),
            polled(id="job-4", state="completed"),
        ]
    )
    reports = RecordedReports()

    result = await _run(task_manager=task_manager, clock=FakeClock(), reports=reports)

    assert result is not None
    assert (result.id, result.state) == ("job-4", CleanupJobState.COMPLETED)
    assert len(task_manager.requests) == 12
    assert reports.waits == [
        CleanupWait.RUNNING_ELSEWHERE,
        CleanupWait.UNKNOWN,
        CleanupWait.UNKNOWN,
        CleanupWait.RUNNING_ELSEWHERE,
        CleanupWait.UNREACHABLE,
    ]


@dataclass
class LastWaitCase:
    name: str
    responses: list[httpx.Response | httpx.TransportError]
    give_up_after: timedelta
    expected_error: str
    expected_waits: list[CleanupWait]


LAST_WAIT_CASES: list[LastWaitCase] = [
    LastWaitCase(
        name="unknown_cleanup",
        responses=[started(), unknown_cleanup()],
        give_up_after=timedelta(seconds=2),
        expected_error=(
            "Gave up after 2 seconds without a cleanup to follow, "
            "when the task manager answered that it does not know the cleanup"
        ),
        expected_waits=[CleanupWait.UNKNOWN],
    ),
    LastWaitCase(
        name="running_elsewhere_after_being_unreachable",
        responses=[started(), unreachable(), unreachable(), unreachable(), unreachable(), running_elsewhere()],
        give_up_after=timedelta(seconds=10),
        expected_error=(
            "Gave up after 10 seconds without a cleanup to follow, "
            "when the task manager answered that a cleanup runs elsewhere"
        ),
        expected_waits=[CleanupWait.UNREACHABLE, CleanupWait.RUNNING_ELSEWHERE],
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in LAST_WAIT_CASES])
@pytest.mark.usefixtures("prefect_client_without_retries")
async def test_giving_up_names_the_reason_to_wait_seen_last(case: LastWaitCase) -> None:
    """The error of a client that gives up names the reason of its last wait, whatever reasons came before."""
    task_manager = ScriptedTaskManager(responses=case.responses)
    reports = RecordedReports()

    with pytest.raises(TaskHistoryCleanupError, match=f"^{re.escape(case.expected_error)}$"):
        await _run(task_manager=task_manager, clock=FakeClock(), reports=reports, give_up_after=case.give_up_after)

    assert len(task_manager.requests) == len(case.responses)
    assert reports.waits == case.expected_waits


async def test_an_answer_showing_the_cleanup_restarts_the_wait_limit() -> None:
    """The wait limit counts from the last answer that showed a cleanup, not from the first request."""
    task_manager = ScriptedTaskManager(
        responses=[
            running_elsewhere(),
            running_elsewhere(),
            running_elsewhere(),
            started(),
            unknown_cleanup(),
            running_elsewhere(),
            started(id="job-2"),
            polled(id="job-2", state="completed"),
        ]
    )
    clock = FakeClock()

    result = await _run(task_manager=task_manager, clock=clock, give_up_after=timedelta(seconds=5))

    assert result is not None
    assert (result.id, result.state) == ("job-2", CleanupJobState.COMPLETED)
    assert len(task_manager.requests) == 8


@pytest.mark.usefixtures("prefect_client_without_retries")
async def test_a_cleanup_the_task_manager_cannot_be_reached_about_is_started_again_after_a_wait() -> None:
    """A task manager unreachable while a cleanup is followed, its restart, is posted to again until it answers."""
    task_manager = ScriptedTaskManager(
        responses=[
            started(),
            polled(current_day="2026-01-15", deleted_runs=4),
            unreachable(),
            unreachable(),
            started(id="job-2"),
            polled(id="job-2", state="completed", current_day="2026-01-16", deleted_runs=2),
        ]
    )
    clock = FakeClock()
    reports = RecordedReports()

    result = await _run(task_manager=task_manager, clock=clock, reports=reports)

    assert result is not None
    assert (result.id, result.state, result.deleted_runs) == ("job-2", CleanupJobState.COMPLETED, 2)
    assert task_manager.requests == [
        RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "never"}),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-1"),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-1"),
        RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "never"}),
        RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "never"}),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-2"),
    ]
    assert reports.progress == [("job-1", date(2026, 1, 15), 4)]
    assert clock.sleeps == [2.0] * 5


async def test_a_task_manager_unreachable_when_the_cleanup_starts_raises_at_once() -> None:
    """A task manager that cannot be reached to start the cleanup raises the transport error, with no wait and no retry."""
    task_manager = ScriptedTaskManager(responses=[unreachable()])
    clock = FakeClock()

    with pytest.raises(httpx.ConnectError, match=r"^All connection attempts failed$"):
        await _run(task_manager=task_manager, clock=clock)

    assert task_manager.requests == [RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "never"})]
    assert clock.sleeps == []


@pytest.mark.usefixtures("prefect_client_without_retries")
async def test_waiting_for_a_cleanup_gives_up_when_the_task_manager_stays_unreachable() -> None:
    """A task manager that stays unreachable after showing a cleanup is posted to until the wait limit, then it gives up."""
    task_manager = ScriptedTaskManager(responses=[started(), *[unreachable() for _ in range(5)]])
    clock = FakeClock()
    reports = RecordedReports()

    with pytest.raises(
        TaskHistoryCleanupError,
        match=r"^Gave up after 10 seconds without a cleanup to follow, when the task manager could not be reached$",
    ):
        await _run(task_manager=task_manager, clock=clock, reports=reports, give_up_after=timedelta(seconds=10))

    assert task_manager.requests == [
        RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "never"}),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-1"),
        *[RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "never"})] * 4,
    ]
    assert clock.sleeps == [2.0] * 5
    assert reports.waits == [CleanupWait.UNREACHABLE]
