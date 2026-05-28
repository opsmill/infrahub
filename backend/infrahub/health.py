from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from infrahub import config
from infrahub.exceptions import InitializationError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices


class DependencyName(StrEnum):
    DATABASE = "database"
    MESSAGE_BUS = "message_bus"
    CACHE = "cache"
    TASK_MANAGER = "task_manager"


class ErrorCategory(StrEnum):
    NONE = "none"
    TIMEOUT = "timeout"
    CONNECTION_REFUSED = "connection_refused"
    CONNECTION_CLOSED = "connection_closed"
    NOT_INITIALIZED = "not_initialized"
    UNKNOWN_ERROR = "unknown_error"


class DependencyStatus(StrEnum):
    UP = "up"
    DOWN = "down"


class OverallStatus(StrEnum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class DependencyHealth(BaseModel):
    name: DependencyName
    status: DependencyStatus
    error: ErrorCategory = ErrorCategory.NONE


class HealthResponse(BaseModel):
    status: OverallStatus
    checks: list[DependencyHealth]
    timestamp: datetime


def classify_error(exc: Exception) -> ErrorCategory:
    if isinstance(exc, TimeoutError | asyncio.TimeoutError):
        return ErrorCategory.TIMEOUT
    if isinstance(exc, InitializationError):
        return ErrorCategory.NOT_INITIALIZED
    if isinstance(exc, ConnectionRefusedError | ConnectionResetError | OSError):
        return ErrorCategory.CONNECTION_REFUSED
    return ErrorCategory.UNKNOWN_ERROR


async def check_dependency(name: DependencyName, probe: Callable[[], Awaitable[bool]]) -> DependencyHealth:
    try:
        healthy = await asyncio.wait_for(probe(), timeout=config.SETTINGS.health.check_timeout)
    except Exception as exc:
        return DependencyHealth(name=name, status=DependencyStatus.DOWN, error=classify_error(exc))
    if healthy:
        return DependencyHealth(name=name, status=DependencyStatus.UP)
    return DependencyHealth(name=name, status=DependencyStatus.DOWN, error=ErrorCategory.UNKNOWN_ERROR)


def determine_status(checks: list[DependencyHealth]) -> OverallStatus:
    """Determine the overall health status from individual dependency checks.

    Returns HEALTHY when all dependencies are up, UNHEALTHY otherwise.
    Enterprise deployments can override this to support degraded states."""
    if all(check.status == DependencyStatus.UP for check in checks):
        return OverallStatus.HEALTHY
    return OverallStatus.UNHEALTHY


async def get_health_checks(service: InfrahubServices, db: InfrahubDatabase) -> list[DependencyHealth]:
    # Wrap service attribute accesses in inner async functions so that
    # InitializationError from a partially-initialized service is caught by
    # check_dependency and reported as DOWN instead of bubbling up as a 500.
    async def probe_message_bus() -> bool:
        return await service.message_bus.is_healthy()

    async def probe_cache() -> bool:
        return await service.cache.is_healthy()

    async def probe_workflow() -> bool:
        return await service.workflow.is_healthy()

    checks = await asyncio.gather(
        check_dependency(DependencyName.DATABASE, db.is_healthy),
        check_dependency(DependencyName.MESSAGE_BUS, probe_message_bus),
        check_dependency(DependencyName.CACHE, probe_cache),
        check_dependency(DependencyName.TASK_MANAGER, probe_workflow),
        return_exceptions=False,
    )
    return list(checks)


async def health_report(service: InfrahubServices, db: InfrahubDatabase) -> HealthResponse:
    checks = await get_health_checks(service=service, db=db)
    status = determine_status(checks)
    return HealthResponse(
        status=status,
        checks=checks,
        timestamp=datetime.now(tz=UTC),
    )
