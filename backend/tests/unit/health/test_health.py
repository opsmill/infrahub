from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from infrahub import config
from infrahub.exceptions import InitializationError
from infrahub.health import (
    DependencyHealth,
    DependencyName,
    DependencyStatus,
    ErrorCategory,
    HealthResponse,
    OverallStatus,
    check_dependency,
    classify_error,
    determine_status,
    get_health_checks,
)
from tests.adapters.cache import MemoryCache
from tests.adapters.health import FailingProbe, HealthyProbe, SlowProbe, UnhealthyProbe
from tests.adapters.message_bus import BusRecorder
from tests.adapters.workflow import WorkflowRecorder


@dataclass
class ClassifyErrorCase:
    id: str
    exception: Exception
    expected: ErrorCategory


CLASSIFY_ERROR_CASES = [
    ClassifyErrorCase(id="timeout_error", exception=TimeoutError(), expected=ErrorCategory.TIMEOUT),
    ClassifyErrorCase(
        id="initialization_error", exception=InitializationError("not ready"), expected=ErrorCategory.NOT_INITIALIZED
    ),
    ClassifyErrorCase(
        id="connection_refused", exception=ConnectionRefusedError(), expected=ErrorCategory.CONNECTION_REFUSED
    ),
    ClassifyErrorCase(
        id="connection_reset", exception=ConnectionResetError(), expected=ErrorCategory.CONNECTION_REFUSED
    ),
    ClassifyErrorCase(id="os_error", exception=OSError("connection failed"), expected=ErrorCategory.CONNECTION_REFUSED),
    ClassifyErrorCase(id="runtime_error", exception=RuntimeError("something"), expected=ErrorCategory.UNKNOWN_ERROR),
    ClassifyErrorCase(id="value_error", exception=ValueError("bad"), expected=ErrorCategory.UNKNOWN_ERROR),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.id) for c in CLASSIFY_ERROR_CASES])
def test_classify_error(case: ClassifyErrorCase) -> None:
    assert classify_error(case.exception) == case.expected


async def test_check_dependency_healthy() -> None:
    result = await check_dependency(DependencyName.DATABASE, HealthyProbe().is_healthy)
    assert result.name == DependencyName.DATABASE
    assert result.status == DependencyStatus.UP
    assert result.error == ErrorCategory.NONE


async def test_check_dependency_returns_false() -> None:
    result = await check_dependency(DependencyName.CACHE, UnhealthyProbe().is_healthy)
    assert result.name == DependencyName.CACHE
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.UNKNOWN_ERROR


async def test_check_dependency_connection_refused() -> None:
    probe = FailingProbe(ConnectionRefusedError())
    result = await check_dependency(DependencyName.MESSAGE_BUS, probe.is_healthy)
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.CONNECTION_REFUSED


async def test_check_dependency_initialization_error() -> None:
    probe = FailingProbe(InitializationError("not ready"))
    result = await check_dependency(DependencyName.TASK_MANAGER, probe.is_healthy)
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.NOT_INITIALIZED


async def test_check_dependency_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.SETTINGS.health, "check_timeout", 1)
    result = await check_dependency(DependencyName.DATABASE, SlowProbe(delay=5).is_healthy)
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.TIMEOUT


def _build_service(*, message_bus: object, cache: object, workflow: object) -> SimpleNamespace:
    return SimpleNamespace(message_bus=message_bus, cache=cache, workflow=workflow)


async def test_get_health_checks_all_healthy() -> None:
    service = _build_service(message_bus=BusRecorder(), cache=MemoryCache(), workflow=WorkflowRecorder())
    db = HealthyProbe()
    checks = await get_health_checks(service=service, db=db)  # type: ignore[arg-type]
    assert len(checks) == 4
    assert all(c.status == DependencyStatus.UP for c in checks)
    assert all(c.error == ErrorCategory.NONE for c in checks)


async def test_get_health_checks_database_down() -> None:
    service = _build_service(message_bus=BusRecorder(), cache=MemoryCache(), workflow=WorkflowRecorder())
    db = UnhealthyProbe()
    checks = await get_health_checks(service=service, db=db)  # type: ignore[arg-type]
    by_name = {c.name: c for c in checks}
    assert by_name[DependencyName.DATABASE].status == DependencyStatus.DOWN
    assert by_name[DependencyName.MESSAGE_BUS].status == DependencyStatus.UP
    assert by_name[DependencyName.CACHE].status == DependencyStatus.UP
    assert by_name[DependencyName.TASK_MANAGER].status == DependencyStatus.UP


async def test_get_health_checks_all_down() -> None:
    service = _build_service(message_bus=UnhealthyProbe(), cache=UnhealthyProbe(), workflow=UnhealthyProbe())
    db = UnhealthyProbe()
    checks = await get_health_checks(service=service, db=db)  # type: ignore[arg-type]
    assert all(c.status == DependencyStatus.DOWN for c in checks)


@dataclass
class DetermineStatusCase:
    id: str
    checks: list[DependencyHealth]
    expected: OverallStatus


DETERMINE_STATUS_CASES = [
    DetermineStatusCase(
        id="all_up",
        checks=[
            DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.UP),
            DependencyHealth(name=DependencyName.MESSAGE_BUS, status=DependencyStatus.UP),
            DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.UP),
        ],
        expected=OverallStatus.HEALTHY,
    ),
    DetermineStatusCase(
        id="one_down",
        checks=[
            DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.DOWN, error=ErrorCategory.TIMEOUT),
            DependencyHealth(name=DependencyName.MESSAGE_BUS, status=DependencyStatus.UP),
            DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.UP),
        ],
        expected=OverallStatus.UNHEALTHY,
    ),
    DetermineStatusCase(
        id="all_down",
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
    DetermineStatusCase(id="empty_checks", checks=[], expected=OverallStatus.HEALTHY),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.id) for c in DETERMINE_STATUS_CASES])
def test_determine_status(case: DetermineStatusCase) -> None:
    assert determine_status(case.checks) == case.expected


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
