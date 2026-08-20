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


async def test_setup_runs_once_across_repeated_calls() -> None:
    setup = RecordingSetup()
    once = TaskManagerSetup(setup=setup)

    await once.run_once()
    await once.run_once()
    await once.run_once()

    assert setup.calls == 1


async def test_failed_setup_is_reported_without_being_rerun() -> None:
    setup = FailingSetup(TimeoutError("prefect server is unreachable"))
    once = TaskManagerSetup(setup=setup)

    with pytest.raises(TimeoutError, match=r"^prefect server is unreachable$"):
        await once.run_once()

    for _ in range(3):
        with pytest.raises(
            RuntimeError, match=r"^Prefect task manager setup already failed in this process$"
        ) as exc_info:
            await once.run_once()
        assert isinstance(exc_info.value.__cause__, TimeoutError)

    assert setup.calls == 1


async def test_failure_that_bypasses_exception_is_remembered() -> None:
    setup = FailingSetup(TimeoutFailure("Timeout >300.0s"))
    once = TaskManagerSetup(setup=setup)

    with pytest.raises(TimeoutFailure, match=r"^Timeout >300\.0s$"):
        await once.run_once()

    with pytest.raises(RuntimeError, match=r"^Prefect task manager setup already failed in this process$"):
        await once.run_once()

    assert setup.calls == 1
