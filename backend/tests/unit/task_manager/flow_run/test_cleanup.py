from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import httpx
import pytest

from infrahub.prefect_server.task_history import CleanupJob, CleanupJobState, CleanupRewrite
from infrahub.task_manager.flow_run.cleanup import TaskHistoryCleanupError, run_task_history_cleanup
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


class ProgressRecorder:
    def __init__(self) -> None:
        self.reported: list[tuple[str, date | None, int]] = []

    def __call__(self, job: CleanupJob) -> None:
        self.reported.append((job.id, job.current_day, job.deleted_runs))


async def _run(
    task_manager: ScriptedTaskManager,
    clock: FakeClock,
    progress: ProgressRecorder | None = None,
    rewrite: CleanupRewrite = CleanupRewrite.NEVER,
    give_up_after: timedelta = timedelta(hours=1),
) -> CleanupJob | None:
    async with task_manager.client() as client:
        return await run_task_history_cleanup(
            client=client,
            rewrite=rewrite,
            on_progress=progress or ProgressRecorder(),
            poll_interval=POLL_INTERVAL,
            give_up_after=give_up_after,
            clock=clock,
            sleep=clock.sleep,
        )


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
    progress = ProgressRecorder()

    result = await _run(task_manager=task_manager, clock=clock, progress=progress, rewrite=CleanupRewrite.IF_FREED)

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
    assert progress.reported == [("job-1", date(2026, 1, 15), 5), ("job-1", date(2026, 1, 16), 9)]
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
    progress = ProgressRecorder()

    result = await _run(task_manager=task_manager, clock=clock, progress=progress)

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
    assert progress.reported == [("job-1", date(2026, 1, 15), 4), ("job-2", date(2026, 1, 16), 2)]
    assert clock.sleeps == [2.0] * 5


async def test_a_failed_cleanup_raises_the_error_the_task_manager_recorded() -> None:
    """A cleanup that ends failed raises with the error the task manager recorded on it."""
    task_manager = ScriptedTaskManager(
        responses=[
            started(),
            polled(
                state="failed",
                error="The cleanup failed with DBAPIError; the task manager log has the details",
            ),
        ]
    )

    with pytest.raises(
        TaskHistoryCleanupError,
        match=r"^The cleanup failed with DBAPIError; the task manager log has the details$",
    ):
        await _run(task_manager=task_manager, clock=FakeClock())


async def test_waiting_for_a_cleanup_gives_up_when_the_task_manager_never_shows_one() -> None:
    """The start is posted again until the task manager has shown no cleanup for the wait limit, then it gives up."""
    task_manager = ScriptedTaskManager(responses=[running_elsewhere() for _ in range(6)])
    clock = FakeClock()

    with pytest.raises(
        TaskHistoryCleanupError,
        match=(
            r"^Gave up after the task manager answered for 10 seconds that a cleanup runs elsewhere "
            r"or that it does not know the cleanup, or could not be reached$"
        ),
    ):
        await _run(task_manager=task_manager, clock=clock, give_up_after=timedelta(seconds=10))

    assert len(task_manager.requests) == 6
    assert clock.sleeps == [2.0] * 5


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


@dataclass
class WeakerRewriteCase:
    name: str
    asked: CleanupRewrite
    running: CleanupRewrite


WEAKER_REWRITE_CASES: list[WeakerRewriteCase] = [
    WeakerRewriteCase(
        name="always_asked_if_freed_running", asked=CleanupRewrite.ALWAYS, running=CleanupRewrite.IF_FREED
    ),
    WeakerRewriteCase(name="always_asked_never_running", asked=CleanupRewrite.ALWAYS, running=CleanupRewrite.NEVER),
    WeakerRewriteCase(name="if_freed_asked_never_running", asked=CleanupRewrite.IF_FREED, running=CleanupRewrite.NEVER),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in WEAKER_REWRITE_CASES])
async def test_a_running_cleanup_with_a_weaker_rewrite_is_followed_by_one_with_the_rewrite_asked_for(
    case: WeakerRewriteCase,
) -> None:
    """A running cleanup started with a weaker rewrite is followed to its end, then the rewrite asked for is posted again."""
    task_manager = ScriptedTaskManager(
        responses=[
            started(rewrite=case.running.value),
            polled(rewrite=case.running.value, current_day="2026-01-15", deleted_runs=5),
            polled(rewrite=case.running.value, state="completed", current_day="2026-01-16", deleted_runs=9),
            started(id="job-2", rewrite=case.asked.value),
            polled(id="job-2", rewrite=case.asked.value, state="completed", rewritten=True),
        ]
    )
    clock = FakeClock()
    progress = ProgressRecorder()

    result = await _run(task_manager=task_manager, clock=clock, progress=progress, rewrite=case.asked)

    assert result is not None
    assert (result.id, result.state, result.rewrite, result.rewritten) == (
        "job-2",
        CleanupJobState.COMPLETED,
        case.asked,
        True,
    )
    assert task_manager.requests == [
        RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": case.asked.value}),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-1"),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-1"),
        RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": case.asked.value}),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-2"),
    ]
    assert progress.reported == [("job-1", date(2026, 1, 15), 5)]
    assert clock.sleeps == [2.0] * 4


@dataclass
class AcceptedRewriteCase:
    name: str
    asked: CleanupRewrite
    running: CleanupRewrite


ACCEPTED_REWRITE_CASES: list[AcceptedRewriteCase] = [
    AcceptedRewriteCase(
        name="never_asked_if_freed_running", asked=CleanupRewrite.NEVER, running=CleanupRewrite.IF_FREED
    ),
    AcceptedRewriteCase(
        name="if_freed_asked_always_running", asked=CleanupRewrite.IF_FREED, running=CleanupRewrite.ALWAYS
    ),
    AcceptedRewriteCase(name="always_asked_always_running", asked=CleanupRewrite.ALWAYS, running=CleanupRewrite.ALWAYS),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in ACCEPTED_REWRITE_CASES])
async def test_a_running_cleanup_with_at_least_the_rewrite_asked_for_is_the_outcome(case: AcceptedRewriteCase) -> None:
    """A running cleanup started with the rewrite asked for, or a stronger one, ends the wait when it completes."""
    task_manager = ScriptedTaskManager(
        responses=[
            started(rewrite=case.running.value),
            polled(rewrite=case.running.value, state="completed", rewritten=True, deleted_runs=4),
        ]
    )
    clock = FakeClock()

    result = await _run(task_manager=task_manager, clock=clock, rewrite=case.asked)

    assert result is not None
    assert (result.id, result.state, result.rewrite, result.deleted_runs) == (
        "job-1",
        CleanupJobState.COMPLETED,
        case.running,
        4,
    )
    assert task_manager.requests == [
        RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": case.asked.value}),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-1"),
    ]
    assert clock.sleeps == [2.0]


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
    progress = ProgressRecorder()

    result = await _run(task_manager=task_manager, clock=clock, progress=progress)

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
    assert progress.reported == [("job-1", date(2026, 1, 15), 4)]
    assert clock.sleeps == [2.0] * 5


@pytest.mark.usefixtures("prefect_client_without_retries")
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

    with pytest.raises(
        TaskHistoryCleanupError,
        match=(
            r"^Gave up after the task manager answered for 10 seconds that a cleanup runs elsewhere "
            r"or that it does not know the cleanup, or could not be reached$"
        ),
    ):
        await _run(task_manager=task_manager, clock=clock, give_up_after=timedelta(seconds=10))

    assert task_manager.requests == [
        RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "never"}),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-1"),
        *[RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "never"})] * 4,
    ]
    assert clock.sleeps == [2.0] * 5
