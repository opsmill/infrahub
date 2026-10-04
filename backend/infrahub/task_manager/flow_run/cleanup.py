from __future__ import annotations

import asyncio
import time
from datetime import timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING

from prefect.exceptions import PrefectHTTPStatusError

from infrahub.exceptions import Error
from infrahub.prefect_server.task_history import CleanupJob, CleanupJobState

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import date

    import httpx
    from prefect.client.orchestration import PrefectClient

    from infrahub.prefect_server.task_history import CleanupRewrite

CLEANUP_PATH = "/infrahub/task-history/cleanup"
POLL_INTERVAL = timedelta(seconds=2)
# Long enough to wait out a cleanup another task manager runs on a large task history, short enough to end a stuck loop.
GIVE_UP_AFTER = timedelta(hours=3)


class TaskHistoryCleanupError(Error):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


async def run_task_history_cleanup(
    client: PrefectClient,
    rewrite: CleanupRewrite,
    on_progress: Callable[[CleanupJob], None],
    poll_interval: timedelta = POLL_INTERVAL,
    give_up_after: timedelta = GIVE_UP_AFTER,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> CleanupJob | None:
    """Run a task history cleanup in the task manager to its end, or return None when the task manager does not provide it.

    A cleanup that runs elsewhere, or that the task manager no longer knows, is started again after a wait; the days
    it already deleted stay deleted. Progress is reported each time the day or the number of deleted runs changes.

    Raises:
        TaskHistoryCleanupError: When the cleanup fails, or when the task manager answers for `give_up_after` only
            that a cleanup runs elsewhere or that it does not know the cleanup.

    """
    job: CleanupJob | None = None
    reported: tuple[date | None, int] | None = None
    last_seen = clock()
    while True:
        if job is None:
            answer = await _answer(request=client._client.post(CLEANUP_PATH, json={"rewrite": rewrite.value}))
            if answer is HTTPStatus.NOT_FOUND:
                return None
        else:
            answer = await _answer(request=client._client.get(f"{CLEANUP_PATH}/{job.id}"))

        if isinstance(answer, CleanupJob):
            job, last_seen = answer, clock()
            if job.state is CleanupJobState.COMPLETED:
                return job
            if job.state is CleanupJobState.FAILED:
                raise TaskHistoryCleanupError(message=job.error or f"The cleanup {job.id} failed")
            progress = (job.current_day, job.deleted_runs)
            if job.current_day is not None and progress != reported:
                on_progress(job)
                reported = progress
        else:
            job = None
            if clock() - last_seen >= give_up_after.total_seconds():
                raise TaskHistoryCleanupError(
                    message=f"Gave up after the task manager answered for {_duration(give_up_after)} "
                    "that a cleanup runs elsewhere or that it does not know the cleanup"
                )
        await sleep(poll_interval.total_seconds())


async def _answer(request: Awaitable[httpx.Response]) -> CleanupJob | HTTPStatus:
    """Return the cleanup in the task manager's answer, or the status of an answer that holds none.

    Raises:
        PrefectHTTPStatusError: When the task manager answers with an error other than 404 or 409.

    """
    try:
        response = await request
    except PrefectHTTPStatusError as exc:
        if exc.response.status_code in {HTTPStatus.NOT_FOUND, HTTPStatus.CONFLICT}:
            return HTTPStatus(exc.response.status_code)
        raise
    return CleanupJob.model_validate_json(response.content)


def _duration(duration: timedelta) -> str:
    seconds = int(duration.total_seconds())
    if seconds < 60:
        return f"{seconds} seconds"
    return f"{seconds // 60} minutes"
