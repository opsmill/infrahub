from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from infrahub.exceptions import InitializationError
from infrahub.health import (
    DependencyHealth,
    DependencyName,
    DependencyStatus,
    ErrorCategory,
    HealthResponse,
    OverallStatus,
    check_cache,
    check_database,
    check_message_bus,
    check_task_manager,
    classify_error,
    determine_status,
    get_health_checks,
)


@dataclass
class ClassifyErrorCase:
    id: str
    exception: Exception
    expected: ErrorCategory


CLASSIFY_ERROR_CASES = [
    ClassifyErrorCase(id="timeout_error", exception=TimeoutError(), expected=ErrorCategory.TIMEOUT),
    ClassifyErrorCase(id="asyncio_timeout_error", exception=TimeoutError(), expected=ErrorCategory.TIMEOUT),
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


@pytest.mark.parametrize(
    "case",
    [pytest.param(c, id=c.id) for c in CLASSIFY_ERROR_CASES],
)
def test_classify_error(case: ClassifyErrorCase) -> None:
    assert classify_error(case.exception) == case.expected


async def test_check_database_healthy() -> None:
    db = AsyncMock()
    db.is_healthy = AsyncMock(return_value=True)
    result = await check_database(db=db)
    assert result.name == DependencyName.DATABASE
    assert result.status == DependencyStatus.UP
    assert result.error is None


async def test_check_database_unhealthy_returns_false() -> None:
    db = AsyncMock()
    db.is_healthy = AsyncMock(return_value=False)
    result = await check_database(db=db)
    assert result.name == DependencyName.DATABASE
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.UNKNOWN_ERROR


async def test_check_database_connection_refused() -> None:
    db = AsyncMock()
    db.is_healthy = AsyncMock(side_effect=ConnectionRefusedError())
    result = await check_database(db=db)
    assert result.name == DependencyName.DATABASE
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.CONNECTION_REFUSED


async def test_check_database_timeout() -> None:
    db = AsyncMock()

    async def slow_check() -> bool:
        await asyncio.sleep(10)
        return True

    db.is_healthy = slow_check
    result = await check_database(db=db)
    assert result.name == DependencyName.DATABASE
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.TIMEOUT


async def test_check_message_bus_healthy() -> None:
    bus = AsyncMock()
    bus.is_healthy = AsyncMock(return_value=True)
    result = await check_message_bus(message_bus=bus)
    assert result.name == DependencyName.MESSAGE_BUS
    assert result.status == DependencyStatus.UP
    assert result.error is None


async def test_check_message_bus_unhealthy_returns_false() -> None:
    bus = AsyncMock()
    bus.is_healthy = AsyncMock(return_value=False)
    result = await check_message_bus(message_bus=bus)
    assert result.name == DependencyName.MESSAGE_BUS
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.UNKNOWN_ERROR


async def test_check_message_bus_initialization_error() -> None:
    bus = AsyncMock()
    bus.is_healthy = AsyncMock(side_effect=InitializationError("not initialized"))
    result = await check_message_bus(message_bus=bus)
    assert result.name == DependencyName.MESSAGE_BUS
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.NOT_INITIALIZED


async def test_check_cache_healthy() -> None:
    cache = AsyncMock()
    cache.is_healthy = AsyncMock(return_value=True)
    result = await check_cache(cache=cache)
    assert result.name == DependencyName.CACHE
    assert result.status == DependencyStatus.UP
    assert result.error is None


async def test_check_cache_unhealthy_returns_false() -> None:
    cache = AsyncMock()
    cache.is_healthy = AsyncMock(return_value=False)
    result = await check_cache(cache=cache)
    assert result.name == DependencyName.CACHE
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.UNKNOWN_ERROR


async def test_check_cache_os_error() -> None:
    cache = AsyncMock()
    cache.is_healthy = AsyncMock(side_effect=OSError("connection failed"))
    result = await check_cache(cache=cache)
    assert result.name == DependencyName.CACHE
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.CONNECTION_REFUSED


async def test_check_task_manager_healthy() -> None:
    workflow = AsyncMock()
    workflow.is_healthy = AsyncMock(return_value=True)
    result = await check_task_manager(workflow=workflow)
    assert result.name == DependencyName.TASK_MANAGER
    assert result.status == DependencyStatus.UP
    assert result.error is None


async def test_check_task_manager_unhealthy_returns_false() -> None:
    workflow = AsyncMock()
    workflow.is_healthy = AsyncMock(return_value=False)
    result = await check_task_manager(workflow=workflow)
    assert result.name == DependencyName.TASK_MANAGER
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.UNKNOWN_ERROR


async def test_check_task_manager_connection_refused() -> None:
    workflow = AsyncMock()
    workflow.is_healthy = AsyncMock(side_effect=ConnectionRefusedError())
    result = await check_task_manager(workflow=workflow)
    assert result.name == DependencyName.TASK_MANAGER
    assert result.status == DependencyStatus.DOWN
    assert result.error == ErrorCategory.CONNECTION_REFUSED


async def test_get_health_checks_all_healthy() -> None:
    db = AsyncMock()
    db.is_healthy = AsyncMock(return_value=True)

    service = MagicMock()
    service.message_bus = AsyncMock()
    service.message_bus.is_healthy = AsyncMock(return_value=True)
    service.cache = AsyncMock()
    service.cache.is_healthy = AsyncMock(return_value=True)
    service.workflow = AsyncMock()
    service.workflow.is_healthy = AsyncMock(return_value=True)

    checks = await get_health_checks(service=service, db=db)
    assert len(checks) == 4
    assert all(c.status == DependencyStatus.UP for c in checks)
    assert all(c.error is None for c in checks)


async def test_get_health_checks_one_down() -> None:
    db = AsyncMock()
    db.is_healthy = AsyncMock(return_value=False)

    service = MagicMock()
    service.message_bus = AsyncMock()
    service.message_bus.is_healthy = AsyncMock(return_value=True)
    service.cache = AsyncMock()
    service.cache.is_healthy = AsyncMock(return_value=True)
    service.workflow = AsyncMock()
    service.workflow.is_healthy = AsyncMock(return_value=True)

    checks = await get_health_checks(service=service, db=db)
    db_check = next(c for c in checks if c.name == DependencyName.DATABASE)
    bus_check = next(c for c in checks if c.name == DependencyName.MESSAGE_BUS)
    cache_check = next(c for c in checks if c.name == DependencyName.CACHE)
    tm_check = next(c for c in checks if c.name == DependencyName.TASK_MANAGER)

    assert db_check.status == DependencyStatus.DOWN
    assert bus_check.status == DependencyStatus.UP
    assert cache_check.status == DependencyStatus.UP
    assert tm_check.status == DependencyStatus.UP


async def test_get_health_checks_all_down() -> None:
    db = AsyncMock()
    db.is_healthy = AsyncMock(return_value=False)

    service = MagicMock()
    service.message_bus = AsyncMock()
    service.message_bus.is_healthy = AsyncMock(return_value=False)
    service.cache = AsyncMock()
    service.cache.is_healthy = AsyncMock(return_value=False)
    service.workflow = AsyncMock()
    service.workflow.is_healthy = AsyncMock(return_value=False)

    checks = await get_health_checks(service=service, db=db)
    assert all(c.status == DependencyStatus.DOWN for c in checks)


def test_determine_status_all_up() -> None:
    checks = [
        DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.UP),
        DependencyHealth(name=DependencyName.MESSAGE_BUS, status=DependencyStatus.UP),
        DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.UP),
    ]
    assert determine_status(checks) == OverallStatus.HEALTHY


def test_determine_status_one_down() -> None:
    checks = [
        DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.DOWN, error=ErrorCategory.TIMEOUT),
        DependencyHealth(name=DependencyName.MESSAGE_BUS, status=DependencyStatus.UP),
        DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.UP),
    ]
    assert determine_status(checks) == OverallStatus.UNHEALTHY


def test_determine_status_all_down() -> None:
    checks = [
        DependencyHealth(
            name=DependencyName.DATABASE, status=DependencyStatus.DOWN, error=ErrorCategory.CONNECTION_REFUSED
        ),
        DependencyHealth(
            name=DependencyName.MESSAGE_BUS, status=DependencyStatus.DOWN, error=ErrorCategory.CONNECTION_CLOSED
        ),
        DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.DOWN, error=ErrorCategory.TIMEOUT),
    ]
    assert determine_status(checks) == OverallStatus.UNHEALTHY


def test_determine_status_empty_checks() -> None:
    assert determine_status([]) == OverallStatus.HEALTHY


def test_healthy_response_model() -> None:
    checks = [
        DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.UP),
        DependencyHealth(name=DependencyName.MESSAGE_BUS, status=DependencyStatus.UP),
        DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.UP),
        DependencyHealth(name=DependencyName.TASK_MANAGER, status=DependencyStatus.UP),
    ]
    response = HealthResponse(status=OverallStatus.HEALTHY, checks=checks, timestamp="2026-03-30T14:00:00Z")
    data = response.model_dump()
    assert data["status"] == "healthy"
    assert len(data["checks"]) == 4
    assert all(c["error"] is None for c in data["checks"])


def test_unhealthy_response_model() -> None:
    checks = [
        DependencyHealth(
            name=DependencyName.DATABASE, status=DependencyStatus.DOWN, error=ErrorCategory.CONNECTION_REFUSED
        ),
        DependencyHealth(name=DependencyName.MESSAGE_BUS, status=DependencyStatus.UP),
        DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.UP),
    ]
    response = HealthResponse(status=OverallStatus.UNHEALTHY, checks=checks, timestamp="2026-03-30T14:00:00Z")
    data = response.model_dump()
    assert data["status"] == "unhealthy"
    db_check = data["checks"][0]
    assert db_check["status"] == "down"
    assert db_check["error"] == "connection_refused"


def test_error_categories_are_strings() -> None:
    check = DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.DOWN, error=ErrorCategory.TIMEOUT)
    data = check.model_dump()
    assert data["error"] == "timeout"
    assert isinstance(data["error"], str)


def test_no_internal_details_in_serialization() -> None:
    checks = [
        DependencyHealth(
            name=DependencyName.DATABASE, status=DependencyStatus.DOWN, error=ErrorCategory.CONNECTION_REFUSED
        ),
    ]
    response = HealthResponse(status=OverallStatus.UNHEALTHY, checks=checks, timestamp="2026-03-30T14:00:00Z")
    json_str = response.model_dump_json()
    assert "localhost" not in json_str
    assert "neo4j://" not in json_str
    assert "redis://" not in json_str
    assert "amqp://" not in json_str
