from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from prefect.settings import PREFECT_API_URL, temporary_settings

from infrahub.exceptions import InitializationError
from infrahub.health import (
    DefaultHealthStatusEvaluator,
    DependencyHealth,
    DependencyName,
    DependencyStatus,
    ErrorCategory,
    HealthChecker,
    HealthResponse,
    OverallStatus,
    check_dependency,
    classify_error,
    probe_task_manager_db,
)
from tests.adapters.cache import MemoryCache
from tests.adapters.health import FailingProbe, HealthyProbe, SlowProbe, UnhealthyProbe
from tests.adapters.message_bus import BusRecorder
from tests.adapters.workflow import WorkflowRecorder

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices


@dataclass
class ClassifyErrorCase:
    name: str
    exception: Exception
    expected: ErrorCategory


CLASSIFY_ERROR_CASES = [
    ClassifyErrorCase(name="timeout_error", exception=TimeoutError(), expected=ErrorCategory.TIMEOUT),
    ClassifyErrorCase(
        name="initialization_error", exception=InitializationError("not ready"), expected=ErrorCategory.NOT_INITIALIZED
    ),
    ClassifyErrorCase(
        name="connection_refused", exception=ConnectionRefusedError(), expected=ErrorCategory.CONNECTION_REFUSED
    ),
    ClassifyErrorCase(
        name="connection_reset", exception=ConnectionResetError(), expected=ErrorCategory.CONNECTION_REFUSED
    ),
    ClassifyErrorCase(
        name="os_error", exception=OSError("connection failed"), expected=ErrorCategory.CONNECTION_REFUSED
    ),
    ClassifyErrorCase(name="runtime_error", exception=RuntimeError("something"), expected=ErrorCategory.UNKNOWN_ERROR),
    ClassifyErrorCase(name="value_error", exception=ValueError("bad"), expected=ErrorCategory.UNKNOWN_ERROR),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in CLASSIFY_ERROR_CASES])
def test_classify_error(case: ClassifyErrorCase) -> None:
    assert classify_error(case.exception) == case.expected


async def test_check_dependency_healthy() -> None:
    result = await check_dependency(DependencyName.DATABASE, HealthyProbe().is_healthy, timeout_seconds=3)
    assert result.name == DependencyName.DATABASE
    assert result.status == DependencyStatus.UP
    assert result.error == ErrorCategory.NONE


async def test_check_dependency_returns_false() -> None:
    result = await check_dependency(DependencyName.CACHE, UnhealthyProbe().is_healthy, timeout_seconds=3)
    assert result.name == DependencyName.CACHE
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.UNKNOWN_ERROR


async def test_check_dependency_connection_refused() -> None:
    probe = FailingProbe(ConnectionRefusedError())
    result = await check_dependency(DependencyName.MESSAGE_BUS, probe.is_healthy, timeout_seconds=3)
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.CONNECTION_REFUSED


async def test_check_dependency_initialization_error() -> None:
    probe = FailingProbe(InitializationError("not ready"))
    result = await check_dependency(DependencyName.TASK_MANAGER, probe.is_healthy, timeout_seconds=3)
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.NOT_INITIALIZED


async def test_check_dependency_timeout() -> None:
    result = await check_dependency(DependencyName.DATABASE, SlowProbe(delay=5).is_healthy, timeout_seconds=1)
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.TIMEOUT


def _build_checker(
    *,
    db: object,
    message_bus: object,
    cache: object,
    workflow: object,
    task_manager_db: object | None = None,
) -> HealthChecker:
    service = SimpleNamespace(message_bus=message_bus, cache=cache, workflow=workflow)
    probe = cast("HealthyProbe", task_manager_db or HealthyProbe())
    return HealthChecker(
        db=cast("InfrahubDatabase", db),
        service=cast("InfrahubServices", service),
        check_timeout=3,
        task_manager_db_probe=probe.is_healthy,
    )


async def test_report_all_healthy() -> None:
    checker = _build_checker(
        db=HealthyProbe(), message_bus=BusRecorder(), cache=MemoryCache(), workflow=WorkflowRecorder()
    )
    report = await checker.report()
    assert report.status == OverallStatus.HEALTHY
    assert len(report.checks) == 5
    assert {c.name for c in report.checks} == set(DependencyName)
    assert all(c.status == DependencyStatus.UP for c in report.checks)
    assert all(c.error == ErrorCategory.NONE for c in report.checks)


async def test_report_database_down() -> None:
    checker = _build_checker(
        db=UnhealthyProbe(), message_bus=BusRecorder(), cache=MemoryCache(), workflow=WorkflowRecorder()
    )
    report = await checker.report()
    assert report.status == OverallStatus.UNHEALTHY
    by_name = {c.name: c for c in report.checks}
    assert by_name[DependencyName.DATABASE].status == DependencyStatus.DOWN
    assert by_name[DependencyName.MESSAGE_BUS].status == DependencyStatus.UP
    assert by_name[DependencyName.CACHE].status == DependencyStatus.UP
    assert by_name[DependencyName.TASK_MANAGER].status == DependencyStatus.UP
    assert by_name[DependencyName.TASK_MANAGER_DB].status == DependencyStatus.UP


@dataclass
class ReportTaskManagerDbCase:
    name: str
    exception: Exception
    expected_error: ErrorCategory


REPORT_TASK_MANAGER_DB_CASES = [
    ReportTaskManagerDbCase(
        name="connection_refused", exception=ConnectionRefusedError(), expected_error=ErrorCategory.CONNECTION_REFUSED
    ),
    ReportTaskManagerDbCase(
        name="not_initialized",
        exception=InitializationError("not configured"),
        expected_error=ErrorCategory.NOT_INITIALIZED,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in REPORT_TASK_MANAGER_DB_CASES])
async def test_report_task_manager_db_down(case: ReportTaskManagerDbCase) -> None:
    checker = _build_checker(
        db=HealthyProbe(),
        message_bus=BusRecorder(),
        cache=MemoryCache(),
        workflow=WorkflowRecorder(),
        task_manager_db=FailingProbe(case.exception),
    )
    report = await checker.report()
    assert report.status == OverallStatus.UNHEALTHY
    by_name = {c.name: c for c in report.checks}
    assert by_name[DependencyName.TASK_MANAGER].status == DependencyStatus.UP
    assert by_name[DependencyName.TASK_MANAGER_DB].status == DependencyStatus.DOWN
    assert by_name[DependencyName.TASK_MANAGER_DB].error == case.expected_error


async def test_report_uninitialized_service() -> None:
    """Service property access raising InitializationError must be reported as DOWN, not bubble up."""

    class _UninitializedService:
        @property
        def message_bus(self) -> object:
            raise InitializationError("Service is not initialized with a message bus")

        @property
        def cache(self) -> object:
            raise InitializationError("Service is not initialized with a cache")

        @property
        def workflow(self) -> object:
            raise InitializationError("Service is not initialized with a workflow")

    checker = HealthChecker(
        db=cast("InfrahubDatabase", HealthyProbe()),
        service=cast("InfrahubServices", _UninitializedService()),
        check_timeout=3,
        task_manager_db_probe=HealthyProbe().is_healthy,
    )
    report = await checker.report()
    assert report.status == OverallStatus.UNHEALTHY
    by_name = {c.name: c for c in report.checks}
    assert by_name[DependencyName.DATABASE].status == DependencyStatus.UP
    assert by_name[DependencyName.MESSAGE_BUS].status == DependencyStatus.DOWN
    assert by_name[DependencyName.MESSAGE_BUS].error == ErrorCategory.NOT_INITIALIZED
    assert by_name[DependencyName.CACHE].error == ErrorCategory.NOT_INITIALIZED
    assert by_name[DependencyName.TASK_MANAGER].error == ErrorCategory.NOT_INITIALIZED
    assert by_name[DependencyName.TASK_MANAGER_DB].status == DependencyStatus.UP


async def test_report_all_down() -> None:
    checker = _build_checker(
        db=UnhealthyProbe(),
        message_bus=UnhealthyProbe(),
        cache=UnhealthyProbe(),
        workflow=UnhealthyProbe(),
        task_manager_db=UnhealthyProbe(),
    )
    report = await checker.report()
    assert report.status == OverallStatus.UNHEALTHY
    assert len(report.checks) == 5
    assert all(c.status == DependencyStatus.DOWN for c in report.checks)


async def test_probe_task_manager_db_not_configured() -> None:
    # With no task manager API configured the probe must report NOT_INITIALIZED rather than fall back
    # to an in-process ephemeral server and report a meaningless UP.
    with temporary_settings(restore_defaults={PREFECT_API_URL}):
        result = await check_dependency(DependencyName.TASK_MANAGER_DB, probe_task_manager_db, timeout_seconds=5)
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.NOT_INITIALIZED


async def test_probe_task_manager_db_unreachable_api() -> None:
    # A refused localhost target proves the probe reaches the task manager API rather than touching a
    # database directly; a connection failure is reported as DOWN with a connection_refused category.
    with temporary_settings({PREFECT_API_URL: "http://127.0.0.1:1/api"}):
        result = await check_dependency(DependencyName.TASK_MANAGER_DB, probe_task_manager_db, timeout_seconds=5)
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.CONNECTION_REFUSED


@dataclass
class EvaluateStatusCase:
    name: str
    checks: list[DependencyHealth]
    expected: OverallStatus


EVALUATE_STATUS_CASES = [
    EvaluateStatusCase(
        name="all_up",
        checks=[
            DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.UP),
            DependencyHealth(name=DependencyName.MESSAGE_BUS, status=DependencyStatus.UP),
            DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.UP),
        ],
        expected=OverallStatus.HEALTHY,
    ),
    EvaluateStatusCase(
        name="one_down",
        checks=[
            DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.DOWN, error=ErrorCategory.TIMEOUT),
            DependencyHealth(name=DependencyName.MESSAGE_BUS, status=DependencyStatus.UP),
            DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.UP),
        ],
        expected=OverallStatus.UNHEALTHY,
    ),
    EvaluateStatusCase(
        name="all_down",
        checks=[
            DependencyHealth(
                name=DependencyName.DATABASE, status=DependencyStatus.DOWN, error=ErrorCategory.CONNECTION_REFUSED
            ),
            DependencyHealth(
                name=DependencyName.MESSAGE_BUS, status=DependencyStatus.DOWN, error=ErrorCategory.CONNECTION_CLOSED
            ),
            DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.DOWN, error=ErrorCategory.TIMEOUT),
        ],
        expected=OverallStatus.UNHEALTHY,
    ),
    EvaluateStatusCase(name="empty_checks", checks=[], expected=OverallStatus.HEALTHY),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in EVALUATE_STATUS_CASES])
def test_default_status_evaluator(case: EvaluateStatusCase) -> None:
    assert DefaultHealthStatusEvaluator().evaluate(case.checks) == case.expected


def test_healthy_response_model() -> None:
    checks = [
        DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.UP),
        DependencyHealth(name=DependencyName.MESSAGE_BUS, status=DependencyStatus.UP),
        DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.UP),
        DependencyHealth(name=DependencyName.TASK_MANAGER, status=DependencyStatus.UP),
    ]
    response = HealthResponse(status=OverallStatus.HEALTHY, checks=checks, timestamp=datetime.now(tz=UTC))
    data = response.model_dump()
    assert data["status"] == "healthy"
    assert len(data["checks"]) == 4
    assert all(c["error"] == "none" for c in data["checks"])


def test_unhealthy_response_model() -> None:
    checks = [
        DependencyHealth(
            name=DependencyName.DATABASE, status=DependencyStatus.DOWN, error=ErrorCategory.CONNECTION_REFUSED
        ),
        DependencyHealth(name=DependencyName.MESSAGE_BUS, status=DependencyStatus.UP),
        DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.UP),
    ]
    response = HealthResponse(status=OverallStatus.UNHEALTHY, checks=checks, timestamp=datetime.now(tz=UTC))
    data = response.model_dump()
    assert data["status"] == "unhealthy"
    db_check = data["checks"][0]
    assert db_check["status"] == "down"
    assert db_check["error"] == "connection_refused"


def test_no_internal_details_in_serialization() -> None:
    checks = [
        DependencyHealth(
            name=DependencyName.DATABASE, status=DependencyStatus.DOWN, error=ErrorCategory.CONNECTION_REFUSED
        ),
    ]
    response = HealthResponse(status=OverallStatus.UNHEALTHY, checks=checks, timestamp=datetime.now(tz=UTC))
    json_str = response.model_dump_json()
    assert "localhost" not in json_str
    assert "neo4j://" not in json_str
    assert "redis://" not in json_str
    assert "amqp://" not in json_str
    assert "postgresql" not in json_str
    assert "asyncpg" not in json_str
    assert ":5432" not in json_str
