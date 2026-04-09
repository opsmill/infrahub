from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from infrahub import config
from infrahub.exceptions import InitializationError

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices
    from infrahub.services.adapters.cache import InfrahubCache
    from infrahub.services.adapters.message_bus import InfrahubMessageBus
    from infrahub.services.adapters.workflow import InfrahubWorkflow


class DependencyName(StrEnum):
    DATABASE = "database"
    MESSAGE_BUS = "message_bus"
    CACHE = "cache"
    TASK_MANAGER = "task_manager"


class ErrorCategory(StrEnum):
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
    error: ErrorCategory | None = None


class HealthResponse(BaseModel):
    status: OverallStatus
    checks: list[DependencyHealth]
    timestamp: str


def classify_error(exc: Exception) -> ErrorCategory:
    if isinstance(exc, TimeoutError | asyncio.TimeoutError):
        return ErrorCategory.TIMEOUT
    if isinstance(exc, InitializationError):
        return ErrorCategory.NOT_INITIALIZED
    if isinstance(exc, ConnectionRefusedError | ConnectionResetError | OSError):
        return ErrorCategory.CONNECTION_REFUSED
    return ErrorCategory.UNKNOWN_ERROR


async def check_database(db: InfrahubDatabase) -> DependencyHealth:
    try:
        healthy = await asyncio.wait_for(db.is_healthy(), timeout=config.SETTINGS.health.check_timeout)
        if healthy:
            return DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.UP)
        return DependencyHealth(
            name=DependencyName.DATABASE, status=DependencyStatus.DOWN, error=ErrorCategory.UNKNOWN_ERROR
        )
    except Exception as exc:
        return DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.DOWN, error=classify_error(exc))


async def check_message_bus(message_bus: InfrahubMessageBus) -> DependencyHealth:
    try:
        healthy = await asyncio.wait_for(message_bus.is_healthy(), timeout=config.SETTINGS.health.check_timeout)
        if healthy:
            return DependencyHealth(name=DependencyName.MESSAGE_BUS, status=DependencyStatus.UP)
        return DependencyHealth(
            name=DependencyName.MESSAGE_BUS, status=DependencyStatus.DOWN, error=ErrorCategory.UNKNOWN_ERROR
        )
    except Exception as exc:
        return DependencyHealth(
            name=DependencyName.MESSAGE_BUS, status=DependencyStatus.DOWN, error=classify_error(exc)
        )


async def check_cache(cache: InfrahubCache) -> DependencyHealth:
    try:
        healthy = await asyncio.wait_for(cache.is_healthy(), timeout=config.SETTINGS.health.check_timeout)
        if healthy:
            return DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.UP)
        return DependencyHealth(
            name=DependencyName.CACHE, status=DependencyStatus.DOWN, error=ErrorCategory.UNKNOWN_ERROR
        )
    except Exception as exc:
        return DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.DOWN, error=classify_error(exc))


async def check_task_manager(workflow: InfrahubWorkflow) -> DependencyHealth:
    try:
        healthy = await asyncio.wait_for(workflow.is_healthy(), timeout=config.SETTINGS.health.check_timeout)
        if healthy:
            return DependencyHealth(name=DependencyName.TASK_MANAGER, status=DependencyStatus.UP)
        return DependencyHealth(
            name=DependencyName.TASK_MANAGER, status=DependencyStatus.DOWN, error=ErrorCategory.UNKNOWN_ERROR
        )
    except Exception as exc:
        return DependencyHealth(
            name=DependencyName.TASK_MANAGER, status=DependencyStatus.DOWN, error=classify_error(exc)
        )


def determine_status(checks: list[DependencyHealth]) -> OverallStatus:
    """Determine the overall health status from individual dependency checks.

    Returns HEALTHY when all dependencies are up, UNHEALTHY otherwise.
    Enterprise deployments can override this to support degraded states."""
    if all(check.status == DependencyStatus.UP for check in checks):
        return OverallStatus.HEALTHY
    return OverallStatus.UNHEALTHY


async def get_health_checks(service: InfrahubServices, db: InfrahubDatabase) -> list[DependencyHealth]:
    checks = await asyncio.gather(
        check_database(db=db),
        check_message_bus(message_bus=service.message_bus),
        check_cache(cache=service.cache),
        check_task_manager(workflow=service.workflow),
        return_exceptions=False,
    )
    return list(checks)


async def health_report(service: InfrahubServices, db: InfrahubDatabase) -> HealthResponse:
    checks = await get_health_checks(service=service, db=db)
    status = determine_status(checks)
    return HealthResponse(
        status=status,
        checks=checks,
        timestamp=datetime.now(tz=UTC).isoformat(),
    )
