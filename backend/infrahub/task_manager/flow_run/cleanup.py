from __future__ import annotations

import asyncio
import time
from datetime import timedelta
from enum import StrEnum
from http import HTTPStatus
from typing import TYPE_CHECKING, assert_never

import httpx
from prefect.exceptions import PrefectHTTPStatusError

from infrahub.exceptions import Error
from infrahub.prefect_server.task_history_models import CleanupJob, CleanupJobState, CleanupRewrite

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import date

    from prefect.client.orchestration import PrefectClient

CLEANUP_PATH = "/infrahub/task-history/cleanup"
POLL_INTERVAL = timedelta(seconds=2)
# Long enough to wait out a cleanup another task manager runs on a large task history, short enough to end a stuck loop.
GIVE_UP_AFTER = timedelta(hours=3)


class CleanupWait(StrEnum):
    """Why there is no cleanup to follow, so that the start is posted again after a wait."""

    RUNNING_ELSEWHERE = "running_elsewhere"
    UNKNOWN = "unknown"
    UNREACHABLE = "unreachable"

    @property
    def reason(self) -> str:
        match self:
            case CleanupWait.RUNNING_ELSEWHERE:
                reason = "the task manager answered that a cleanup runs elsewhere"
            case CleanupWait.UNKNOWN:
                reason = "the task manager answered that it does not know the cleanup"
            case CleanupWait.UNREACHABLE:
                reason = "the task manager could not be reached"
            case _:
                assert_never(self)
        return reason


class TaskHistoryCleanupError(Error):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class TaskHistoryCleanupFailedError(TaskHistoryCleanupError):
    """A cleanup that ended failed in the task manager, with the job as it ended, which holds what it had done."""

    def __init__(self, job: CleanupJob) -> None:
        self.job = job
        super().__init__(message=job.error or f"The cleanup {job.id} failed")


async def run_task_history_cleanup(
    client: PrefectClient,
    rewrite: CleanupRewrite,
    on_progress: Callable[[CleanupJob], None],
    on_wait: Callable[[CleanupWait], None],
    poll_interval: timedelta = POLL_INTERVAL,
    give_up_after: timedelta = GIVE_UP_AFTER,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> CleanupJob | None:
    """Run a task history cleanup in the task manager to its end, or return None when the task manager does not provide it.

    A cleanup already running in the task manager is followed instead, the task manager raising its rewrite to the
    one asked for when that is stronger. A cleanup that runs elsewhere, that the task manager no longer knows, or
    that the task manager cannot be reached about once it answered, is started again after a wait; the days it
    already deleted stay deleted. Progress is reported each time the day or the number of deleted runs changes, and
    a wait when it starts, when its reason changes, and when it starts again after a cleanup showed.

    Raises:
        TaskHistoryCleanupFailedError: When the cleanup fails in the task manager.
        TaskHistoryCleanupError: When the task manager shows no cleanup for `give_up_after`, naming the reason of
            the last wait.
        httpx.TransportError: When the task manager cannot be reached to start the cleanup.
        PrefectHTTPStatusError: When the task manager answers with an error other than 404 or 409.

    """
    job: CleanupJob | None = None
    answered = False
    reported: tuple[date | None, int] | None = None
    waiting: CleanupWait | None = None
    last_seen = clock()
    while True:
        request = (
            client._client.post(CLEANUP_PATH, json={"rewrite": rewrite.value})
            if (posted := job is None)
            else client._client.get(f"{CLEANUP_PATH}/{job.id}")
        )
        try:
            answer = await _answer(request=request, posted=posted)
        except httpx.TransportError:
            # Unreachable after it answered is a restart, which loses the cleanup as an unknown one does.
            if not answered:
                raise
            answer = CleanupWait.UNREACHABLE
        answered = True
        if answer is None:
            return None

        if isinstance(answer, CleanupJob):
            job, last_seen, waiting = answer, clock(), None
            if job.state is CleanupJobState.COMPLETED:
                return job
            if job.state is CleanupJobState.FAILED:
                raise TaskHistoryCleanupFailedError(job=job)
            progress = (job.current_day, job.deleted_runs)
            if job.current_day is not None and progress != reported:
                on_progress(job)
                reported = progress
        else:
            job = None
            if answer is not waiting:
                on_wait(answer)
                waiting = answer
            if clock() - last_seen >= give_up_after.total_seconds():
                raise TaskHistoryCleanupError(
                    message=f"Gave up after {_duration(give_up_after)} without a cleanup to follow, when {answer.reason}"
                )
        await sleep(poll_interval.total_seconds())


async def _answer(request: Awaitable[httpx.Response], posted: bool) -> CleanupJob | CleanupWait | None:
    """Return the cleanup in the task manager's answer, why it holds none, or None when it does not provide the cleanup.

    Raises:
        PrefectHTTPStatusError: When the task manager answers with an error other than 404 or 409.

    """
    try:
        response = await request
    except PrefectHTTPStatusError as exc:
        match exc.response.status_code:
            case HTTPStatus.CONFLICT:
                return CleanupWait.RUNNING_ELSEWHERE
            case HTTPStatus.NOT_FOUND:
                # A start answered with 404 reached a task manager without the route; a read, one that lost the cleanup.
                return None if posted else CleanupWait.UNKNOWN
            case _:
                raise
    return CleanupJob.model_validate_json(response.content)


def _duration(duration: timedelta) -> str:
    seconds = int(duration.total_seconds())
    if seconds < 60:
        return f"{seconds} seconds"
    return f"{seconds // 60} minutes"
