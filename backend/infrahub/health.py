from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

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
    TASK_MANAGER_DB = "task_manager_db"


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


async def check_dependency(
    name: DependencyName, probe: Callable[[], Awaitable[bool]], *, timeout_seconds: float
) -> DependencyHealth:
    try:
        healthy = await asyncio.wait_for(probe(), timeout=timeout_seconds)
    except Exception as exc:
        return DependencyHealth(name=name, status=DependencyStatus.DOWN, error=classify_error(exc))
    if healthy:
        return DependencyHealth(name=name, status=DependencyStatus.UP)
    return DependencyHealth(name=name, status=DependencyStatus.DOWN, error=ErrorCategory.UNKNOWN_ERROR)


class HealthStatusEvaluator(Protocol):
    """Aggregates individual dependency checks into a single overall status.

    Implementations choose the aggregation policy. The default treats any DOWN
    dependency as UNHEALTHY; an alternative implementation can introduce a
    degraded state without changing how the dependencies themselves are probed.
    """

    def evaluate(self, checks: list[DependencyHealth]) -> OverallStatus: ...


class DefaultHealthStatusEvaluator:
    """Overall status is HEALTHY only when every dependency reports UP."""

    def evaluate(self, checks: list[DependencyHealth]) -> OverallStatus:
        if all(check.status == DependencyStatus.UP for check in checks):
            return OverallStatus.HEALTHY
        return OverallStatus.UNHEALTHY


class HealthChecker:
    """Probes the backing services Infrahub needs to serve traffic and reports their health."""

    def __init__(
        self,
        db: InfrahubDatabase,
        service: InfrahubServices,
        *,
        check_timeout: float,
        task_manager_db_probe: Callable[[], Awaitable[bool]],
        status_evaluator: HealthStatusEvaluator | None = None,
    ) -> None:
        self._db = db
        self._service = service
        self._check_timeout = check_timeout
        self._task_manager_db_probe = task_manager_db_probe
        self._status_evaluator = status_evaluator or DefaultHealthStatusEvaluator()

    async def report(self) -> HealthResponse:
        checks = await self._run_checks()
        return HealthResponse(
            status=self._status_evaluator.evaluate(checks),
            checks=checks,
            timestamp=datetime.now(tz=UTC),
        )

    async def _run_checks(self) -> list[DependencyHealth]:
        # Service attribute access is deferred into inner coroutines so that an
        # error raised by a partially-initialized service is caught per dependency
        # and reported as DOWN instead of failing the whole report.
        async def probe_message_bus() -> bool:
            return await self._service.message_bus.is_healthy()

        async def probe_cache() -> bool:
            return await self._service.cache.is_healthy()

        async def probe_workflow() -> bool:
            return await self._service.workflow.is_healthy()

        checks = await asyncio.gather(
            check_dependency(DependencyName.DATABASE, self._db.is_healthy, timeout_seconds=self._check_timeout),
            check_dependency(DependencyName.MESSAGE_BUS, probe_message_bus, timeout_seconds=self._check_timeout),
            check_dependency(DependencyName.CACHE, probe_cache, timeout_seconds=self._check_timeout),
            check_dependency(DependencyName.TASK_MANAGER, probe_workflow, timeout_seconds=self._check_timeout),
            check_dependency(
                DependencyName.TASK_MANAGER_DB, self._task_manager_db_probe, timeout_seconds=self._check_timeout
            ),
        )
        return list(checks)


TASK_MANAGER_DB_CONNECTION_URL_ENV = "PREFECT_API_DATABASE_CONNECTION_URL"


async def probe_task_manager_db() -> bool:
    """Probe the task manager's backing store using the connection URL the task manager itself uses.

    The URL is read from the environment rather than the task manager's resolved settings so that an
    unset value is treated as not-configured, instead of silently probing the task manager's default
    local store.

    Raises:
        InitializationError: When the connection URL is not configured.

    """
    connection_url = os.environ.get(TASK_MANAGER_DB_CONNECTION_URL_ENV)
    if not connection_url:
        raise InitializationError("Task manager database connection URL is not configured")

    engine = create_async_engine(connection_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    finally:
        # Never let a disposal error mask the probe's real failure (timeout / connection error).
        # suppress(Exception) leaves CancelledError untouched, so timeout classification is preserved.
        with suppress(Exception):
            await engine.dispose()
    return True
