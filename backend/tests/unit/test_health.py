from __future__ import annotations

import asyncio
import errno
import socket
from dataclasses import dataclass, field

import pytest

from infrahub.exceptions import DependencyConnectionClosedError, DependencyUnhealthyError
from infrahub.health import (
    DependencyCheck,
    DependencyHealth,
    DependencyName,
    DependencyStatus,
    ErrorCategory,
    HealthChecker,
    HealthStatus,
    build_health_checker,
    classify_error,
)

SECRET_IN_ERROR = "redis://admin:s3cret@cache.internal:6379"
CHECK_TIMEOUT = 0.2


def _chained(outer: BaseException, cause: BaseException) -> BaseException:
    outer.__cause__ = cause
    return outer


def _implicitly_chained(outer: BaseException, context: BaseException) -> BaseException:
    outer.__context__ = context
    return outer


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@dataclass
class RecordingCheck:
    """Counts its calls and fails with ``error`` when one is set."""

    error: BaseException | None = None
    delay: float = 0.0
    calls: int = field(default=0, init=False)

    async def __call__(self) -> None:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error


def _checker(
    *checks: tuple[DependencyName, RecordingCheck], clock: FakeClock, max_report_age: float = 0.0
) -> HealthChecker:
    return HealthChecker(
        checks=[DependencyCheck(name=name, check=check) for name, check in checks],
        check_timeout=CHECK_TIMEOUT,
        max_report_age=max_report_age,
        clock=clock,
    )


@dataclass
class ClassifyErrorTestCase:
    name: str
    error: BaseException
    expected: ErrorCategory


CLASSIFY_ERROR_TEST_CASES: list[ClassifyErrorTestCase] = [
    ClassifyErrorTestCase(name="timeout", error=TimeoutError(), expected=ErrorCategory.TIMEOUT),
    ClassifyErrorTestCase(
        name="refused_connection_built_from_errno",
        error=OSError(errno.ECONNREFUSED, "Connect call failed ('10.0.0.1', 6379)"),
        expected=ErrorCategory.CONNECTION_REFUSED,
    ),
    ClassifyErrorTestCase(
        name="refused_connection_wrapped_by_a_driver_error",
        error=_chained(RuntimeError("Couldn't connect to database:7687"), ConnectionRefusedError()),
        expected=ErrorCategory.CONNECTION_REFUSED,
    ),
    ClassifyErrorTestCase(
        name="unresolvable_name_two_levels_down",
        error=_chained(
            RuntimeError("Error connecting to cache:6379"),
            _chained(OSError("lookup failed"), socket.gaierror(socket.EAI_NONAME, "Name or service not known")),
        ),
        expected=ErrorCategory.NAME_RESOLUTION_FAILED,
    ),
    ClassifyErrorTestCase(
        name="timeout_raised_while_handling_another_error",
        error=_implicitly_chained(RuntimeError("request failed"), TimeoutError()),
        expected=ErrorCategory.TIMEOUT,
    ),
    ClassifyErrorTestCase(
        name="refused_on_every_address_of_a_name",
        error=_chained(
            OSError("All connection attempts failed"),
            ExceptionGroup(
                "multiple connection attempts failed",
                [
                    ConnectionRefusedError(errno.ECONNREFUSED, "Connect call failed ('::1', 4200, 0, 0)"),
                    ConnectionRefusedError(errno.ECONNREFUSED, "Connect call failed ('127.0.0.1', 4200)"),
                ],
            ),
        ),
        expected=ErrorCategory.CONNECTION_REFUSED,
    ),
    ClassifyErrorTestCase(
        name="connection_reset", error=ConnectionResetError(), expected=ErrorCategory.CONNECTION_CLOSED
    ),
    ClassifyErrorTestCase(name="broken_pipe", error=BrokenPipeError(), expected=ErrorCategory.CONNECTION_CLOSED),
    ClassifyErrorTestCase(
        name="closed_connection_reported_by_an_adapter",
        error=_chained(DependencyConnectionClosedError(message="closed"), RuntimeError("No active transport")),
        expected=ErrorCategory.CONNECTION_CLOSED,
    ),
    ClassifyErrorTestCase(
        name="service_answered_that_it_cannot_serve",
        error=_chained(DependencyUnhealthyError(message="refused a write"), RuntimeError("OOM command not allowed")),
        expected=ErrorCategory.UNAVAILABLE,
    ),
    ClassifyErrorTestCase(
        name="outermost_category_wins",
        error=_chained(DependencyUnhealthyError(message="refused a write"), ConnectionResetError()),
        expected=ErrorCategory.UNAVAILABLE,
    ),
    ClassifyErrorTestCase(
        name="error_without_a_known_cause", error=RuntimeError("unexpected"), expected=ErrorCategory.UNKNOWN_ERROR
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in CLASSIFY_ERROR_TEST_CASES])
def test_classify_error(test_case: ClassifyErrorTestCase) -> None:
    assert classify_error(test_case.error) == test_case.expected


def test_classify_error_stops_on_a_cyclic_chain() -> None:
    first = RuntimeError("first")
    second = RuntimeError("second")
    first.__cause__ = second
    second.__cause__ = first

    assert classify_error(first) == ErrorCategory.UNKNOWN_ERROR


async def test_report_is_healthy_when_every_check_passes() -> None:
    checker = _checker(
        (DependencyName.DATABASE, RecordingCheck()), (DependencyName.CACHE, RecordingCheck()), clock=FakeClock()
    )

    report = await checker.report()

    assert report.status == HealthStatus.HEALTHY
    assert report.dependencies == [
        DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.UP, error=ErrorCategory.NONE),
        DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.UP, error=ErrorCategory.NONE),
    ]


async def test_one_failing_check_makes_the_report_unhealthy_and_the_others_still_run() -> None:
    database = RecordingCheck()
    cache = RecordingCheck(error=_chained(RuntimeError(SECRET_IN_ERROR), ConnectionRefusedError()))
    task_manager = RecordingCheck()
    checker = _checker(
        (DependencyName.DATABASE, database),
        (DependencyName.CACHE, cache),
        (DependencyName.TASK_MANAGER, task_manager),
        clock=FakeClock(),
    )

    report = await checker.report()

    assert report.status == HealthStatus.UNHEALTHY
    assert report.dependencies == [
        DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.UP, error=ErrorCategory.NONE),
        DependencyHealth(
            name=DependencyName.CACHE, status=DependencyStatus.DOWN, error=ErrorCategory.CONNECTION_REFUSED
        ),
        DependencyHealth(name=DependencyName.TASK_MANAGER, status=DependencyStatus.UP, error=ErrorCategory.NONE),
    ]
    assert (database.calls, cache.calls, task_manager.calls) == (1, 1, 1)


async def test_report_never_contains_the_error_message() -> None:
    checker = _checker((DependencyName.CACHE, RecordingCheck(error=RuntimeError(SECRET_IN_ERROR))), clock=FakeClock())

    report = await checker.report()

    serialized = report.model_dump_json()
    assert "s3cret" not in serialized
    assert "cache.internal" not in serialized
    assert report.dependencies[0].error == ErrorCategory.UNKNOWN_ERROR


async def test_a_check_slower_than_the_timeout_is_reported_as_a_timeout() -> None:
    slow = RecordingCheck(delay=CHECK_TIMEOUT * 20)
    checker = _checker(
        (DependencyName.DATABASE, RecordingCheck()), (DependencyName.MESSAGE_BUS, slow), clock=FakeClock()
    )

    report = await checker.report()

    assert report.status == HealthStatus.UNHEALTHY
    assert report.dependencies[1] == DependencyHealth(
        name=DependencyName.MESSAGE_BUS, status=DependencyStatus.DOWN, error=ErrorCategory.TIMEOUT
    )


async def test_report_is_reused_until_it_is_older_than_the_maximum_age() -> None:
    clock = FakeClock()
    check = RecordingCheck()
    checker = _checker((DependencyName.DATABASE, check), clock=clock, max_report_age=1.0)

    first = await checker.report()
    clock.now = 0.9
    reused = await checker.report()
    clock.now = 1.0
    refreshed = await checker.report()

    assert reused is first
    assert refreshed is not first
    assert check.calls == 2


async def test_concurrent_callers_share_one_round_of_checks() -> None:
    check = RecordingCheck(delay=CHECK_TIMEOUT / 4)
    checker = _checker((DependencyName.DATABASE, check), clock=FakeClock(), max_report_age=1.0)

    reports = await asyncio.gather(*(checker.report() for _ in range(20)))

    assert check.calls == 1
    assert all(report is reports[0] for report in reports)


class FailingService:
    """Fails its health check with ``error``."""

    def __init__(self, error: BaseException) -> None:
        self.error = error

    async def check_health(self) -> None:
        raise self.error


class FailingTaskManager(FailingService):
    """Fails its own check with ``error`` and the check of its database with ``database_error``."""

    def __init__(self, error: BaseException, database_error: BaseException) -> None:
        super().__init__(error=error)
        self.database_error = database_error

    async def check_database_health(self) -> None:
        raise self.database_error


async def test_each_service_is_reported_under_its_own_name() -> None:
    checker = build_health_checker(
        database=FailingService(error=TimeoutError()),
        message_bus=FailingService(error=DependencyConnectionClosedError(message="closed")),
        cache=FailingService(error=ConnectionRefusedError()),
        workflow=FailingTaskManager(
            error=socket.gaierror(socket.EAI_NONAME, "Name or service not known"),
            database_error=DependencyUnhealthyError(message="database unavailable"),
        ),
        check_timeout=CHECK_TIMEOUT,
    )

    report = await checker.report()

    assert [(dependency.name, dependency.error) for dependency in report.dependencies] == [
        (DependencyName.DATABASE, ErrorCategory.TIMEOUT),
        (DependencyName.MESSAGE_BUS, ErrorCategory.CONNECTION_CLOSED),
        (DependencyName.CACHE, ErrorCategory.CONNECTION_REFUSED),
        (DependencyName.TASK_MANAGER, ErrorCategory.NAME_RESOLUTION_FAILED),
        (DependencyName.TASK_MANAGER_DB, ErrorCategory.UNAVAILABLE),
    ]
