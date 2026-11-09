import asyncio
import gc
import logging
import time

import pytest

from tests.helpers.task_manager import TaskManagerSetup


class TimeoutFailure(BaseException):
    """Stands in for pytest's Failed, which derives from BaseException rather than Exception."""


class RecordingSetup:
    """Counts how many times the task manager setup was actually run."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self) -> None:
        self.calls += 1


class FailingSetup(RecordingSetup):
    """Stands in for a Prefect test server that accepts connections but never answers."""

    def __init__(self, error: BaseException) -> None:
        super().__init__()
        self.error = error

    async def __call__(self) -> None:
        await super().__call__()
        raise self.error


class MovingServer:
    """Stands in for the settings lookup, so a test can move the API URL between calls."""

    def __init__(self, url: str | None = "http://server-a/api") -> None:
        self.url = url

    def __call__(self) -> str | None:
        return self.url


async def test_setup_runs_once_across_repeated_calls() -> None:
    setup = RecordingSetup()
    once = TaskManagerSetup(setup=setup, server_key=MovingServer())

    await once.run_once()
    await once.run_once()
    await once.run_once()

    assert setup.calls == 1


async def test_setup_runs_again_for_a_different_server() -> None:
    """A process talks to several Prefect servers; each needs its own deployments registered."""
    setup = RecordingSetup()
    server = MovingServer("http://harness/api")
    once = TaskManagerSetup(setup=setup, server_key=server)

    await once.run_once()
    server.url = "http://container/api"
    await once.run_once()
    await once.run_once()

    assert setup.calls == 2

    # Coming back to the first server still reuses its setup.
    server.url = "http://harness/api"
    await once.run_once()

    assert setup.calls == 2


async def test_failed_setup_is_reported_without_being_rerun() -> None:
    setup = FailingSetup(TimeoutError("prefect server is unreachable"))
    once = TaskManagerSetup(setup=setup, server_key=MovingServer("http://server-a/api"))

    with pytest.raises(TimeoutError, match=r"^prefect server is unreachable$"):
        await once.run_once()

    for _ in range(3):
        with pytest.raises(
            RuntimeError, match=r"^Prefect task manager setup already failed for http://server-a/api$"
        ) as exc_info:
            await once.run_once()
        assert isinstance(exc_info.value.__cause__, TimeoutError)

    assert setup.calls == 1


async def test_failure_is_remembered_per_server() -> None:
    """One unreachable server must not condemn the next one the process points at."""
    setup = FailingSetup(TimeoutError("prefect server is unreachable"))
    server = MovingServer("http://broken/api")
    once = TaskManagerSetup(setup=setup, server_key=server)

    with pytest.raises(TimeoutError):
        await once.run_once()

    server.url = "http://healthy/api"
    with pytest.raises(TimeoutError):
        await once.run_once()

    assert setup.calls == 2


async def test_failure_that_bypasses_exception_is_remembered() -> None:
    setup = FailingSetup(TimeoutFailure("Timeout >300.0s"))
    once = TaskManagerSetup(setup=setup, server_key=MovingServer("http://server-a/api"))

    with pytest.raises(TimeoutFailure, match=r"^Timeout >300\.0s$"):
        await once.run_once()

    with pytest.raises(RuntimeError, match=r"^Prefect task manager setup already failed for http://server-a/api$"):
        await once.run_once()

    assert setup.calls == 1


class HangingSetup(RecordingSetup):
    """Stands in for a Prefect test server that accepts connections but never answers."""

    async def __call__(self) -> None:
        await super().__call__()
        await asyncio.Event().wait()


class RecordingReport:
    """Keeps the diagnostic reports a failed setup asked for."""

    def __init__(self) -> None:
        self.reasons: list[str] = []

    def __call__(self, reason: str) -> None:
        self.reasons.append(reason)


async def test_hanging_setup_gives_up_inside_the_coroutine() -> None:
    """The pytest timeout fires above the coroutine, so a hang has to be bounded here."""
    setup = HangingSetup()
    once = TaskManagerSetup(setup=setup, server_key=MovingServer("http://wedged/api"), timeout=0.05)

    with pytest.raises(TimeoutError):
        await once.run_once()

    with pytest.raises(RuntimeError, match=r"^Prefect task manager setup already failed for http://wedged/api$"):
        await once.run_once()

    assert setup.calls == 1


class LoopBlockingSetup(RecordingSetup):
    """Stands in for Prefect's synchronous HTTP call at flow start, ended by the pytest timeout."""

    def __init__(self, blocked_for: float, error: BaseException) -> None:
        super().__init__()
        self.blocked_for = blocked_for
        self.error = error

    async def __call__(self) -> None:
        await super().__call__()
        time.sleep(self.blocked_for)  # noqa: ASYNC251 - blocking the loop is the point of this double
        raise self.error


async def test_a_failure_raised_inside_a_setup_that_blocked_the_loop_past_the_ceiling_is_remembered() -> None:
    """The ceiling is a loop timer and cannot fire while the loop is blocked.

    The failure that ends the block is the one worth remembering, not a timeout dressed up after
    the fact.
    """
    setup = LoopBlockingSetup(blocked_for=0.1, error=TimeoutFailure("Timeout >300.0s"))
    once = TaskManagerSetup(setup=setup, server_key=MovingServer("http://blocked/api"), timeout=0.02)

    with pytest.raises(TimeoutFailure, match=r"^Timeout >300\.0s$"):
        await once.run_once()

    with pytest.raises(
        RuntimeError, match=r"^Prefect task manager setup already failed for http://blocked/api$"
    ) as exc_info:
        await once.run_once()

    assert isinstance(exc_info.value.__cause__, TimeoutFailure)
    assert setup.calls == 1


class CrashHandlingSetup(RecordingSetup):
    """Stands in for a Prefect flow whose cancellation is answered by a shielded state write.

    The engine writes a Crashed state to the server the setup was talking to before it lets the
    cancellation through. Against a wedged server that write itself hangs.
    """

    def __init__(self, crash_handling_seconds: float, ends_with: BaseException | None = None) -> None:
        super().__init__()
        self.crash_handling_seconds = crash_handling_seconds
        self.ends_with = ends_with
        """What the crash handling raises in place of the cancellation, when it fails on its own."""
        self.crash_handling_started = asyncio.Event()
        self.finished = asyncio.Event()

    async def __call__(self) -> None:
        await super().__call__()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.crash_handling_started.set()
            try:
                await asyncio.sleep(self.crash_handling_seconds)
            finally:
                self.finished.set()
            if self.ends_with is not None:
                raise self.ends_with from None
            raise


async def test_a_timed_out_setup_is_remembered_before_its_cancellation_is_handled() -> None:
    """The memo cannot depend on the setup unwinding: against a wedged server that takes minutes."""
    setup = CrashHandlingSetup(crash_handling_seconds=0.5)
    report = RecordingReport()
    once = TaskManagerSetup(
        setup=setup,
        server_key=MovingServer("http://wedged/api"),
        timeout=0.05,
        crash_handling_grace=0.05,
        report_failure=report,
    )

    with pytest.raises(TimeoutError, match=r"^Prefect task manager setup did not finish within 0s$"):
        await once.run_once()

    assert setup.crash_handling_started.is_set()
    assert not setup.finished.is_set(), "giving up must not wait for the crash handling"
    assert report.reasons == [
        "Prefect task manager setup failed for http://wedged/api: "
        "TimeoutError('Prefect task manager setup did not finish within 0s')"
    ]

    with pytest.raises(
        RuntimeError, match=r"^Prefect task manager setup already failed for http://wedged/api$"
    ) as exc_info:
        await once.run_once()

    assert isinstance(exc_info.value.__cause__, TimeoutError)
    assert setup.calls == 1
    assert len(report.reasons) == 1

    await asyncio.wait_for(setup.finished.wait(), timeout=2)


async def test_a_timed_out_setup_that_finishes_its_bookkeeping_is_not_left_behind() -> None:
    setup = CrashHandlingSetup(crash_handling_seconds=0)
    once = TaskManagerSetup(
        setup=setup, server_key=MovingServer("http://slow/api"), timeout=0.05, crash_handling_grace=1
    )

    with pytest.raises(TimeoutError):
        await once.run_once()

    assert setup.finished.is_set()


async def test_how_a_cancelled_setup_ended_is_kept_with_the_timeout() -> None:
    """A crash write that fails on its own is a cause worth reading, not noise to hide behind the timeout."""
    setup = CrashHandlingSetup(crash_handling_seconds=0, ends_with=RuntimeError("state write refused"))
    once = TaskManagerSetup(
        setup=setup, server_key=MovingServer("http://slow/api"), timeout=0.05, crash_handling_grace=1
    )

    with pytest.raises(TimeoutError) as exc_info:
        await once.run_once()

    assert exc_info.value.__notes__ == [
        "After the cancellation the setup ended with RuntimeError('state write refused')"
    ]


async def test_cancelling_the_caller_cancels_the_setup(caplog: pytest.LogCaptureFixture) -> None:
    setup = CrashHandlingSetup(crash_handling_seconds=0, ends_with=RuntimeError("state write refused"))
    once = TaskManagerSetup(setup=setup, server_key=MovingServer("http://server-a/api"), timeout=60)

    with caplog.at_level(logging.ERROR, logger="asyncio"):
        caller = asyncio.ensure_future(once.run_once())
        await asyncio.sleep(0)
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller

        await asyncio.wait_for(setup.finished.wait(), timeout=1)
        # The setup task has no reader left; asyncio reports an unread outcome when it is collected.
        del caller
        gc.collect()

    assert not [record for record in caplog.records if "never retrieved" in record.getMessage()]


async def test_a_failed_setup_is_reported_once() -> None:
    setup = FailingSetup(TimeoutError("prefect server is unreachable"))
    report = RecordingReport()
    once = TaskManagerSetup(setup=setup, server_key=MovingServer("http://server-a/api"), report_failure=report)

    with pytest.raises(TimeoutError):
        await once.run_once()
    with pytest.raises(RuntimeError):
        await once.run_once()

    assert report.reasons == [
        "Prefect task manager setup failed for http://server-a/api: TimeoutError('prefect server is unreachable')"
    ]


async def test_a_successful_setup_is_not_reported() -> None:
    report = RecordingReport()
    once = TaskManagerSetup(setup=RecordingSetup(), server_key=MovingServer(), report_failure=report)

    await once.run_once()

    assert report.reasons == []
