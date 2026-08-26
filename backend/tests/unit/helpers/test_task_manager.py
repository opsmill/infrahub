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
