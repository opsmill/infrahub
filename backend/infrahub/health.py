from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

import httpx
from prefect.client.orchestration import get_client
from prefect.settings import PREFECT_CLIENT_MAX_RETRIES, get_current_settings, temporary_settings
from pydantic import BaseModel

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
    if isinstance(exc, TimeoutError | asyncio.TimeoutError | httpx.TimeoutException):
        return ErrorCategory.TIMEOUT
    if isinstance(exc, InitializationError):
        return ErrorCategory.NOT_INITIALIZED
    if isinstance(exc, ConnectionRefusedError | ConnectionResetError | OSError | httpx.ConnectError):
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


async def gather_dependency_health(
    *,
    database_probe: Callable[[], Awaitable[bool]],
    message_bus_probe: Callable[[], Awaitable[bool]],
    cache_probe: Callable[[], Awaitable[bool]],
    task_manager_probe: Callable[[], Awaitable[bool]],
    task_manager_db_probe: Callable[[], Awaitable[bool]],
    check_timeout: float,
) -> list[DependencyHealth]:
    """Probe every backing dependency concurrently and return their individual health.

    Each probe is a no-argument coroutine so that resolving or accessing the underlying
    collaborator happens inside the per-dependency timeout-and-catch boundary: a collaborator
    that is missing or unreachable is reported as DOWN rather than aborting the whole set.
    """
    checks = await asyncio.gather(
        check_dependency(DependencyName.DATABASE, database_probe, timeout_seconds=check_timeout),
        check_dependency(DependencyName.MESSAGE_BUS, message_bus_probe, timeout_seconds=check_timeout),
        check_dependency(DependencyName.CACHE, cache_probe, timeout_seconds=check_timeout),
        check_dependency(DependencyName.TASK_MANAGER, task_manager_probe, timeout_seconds=check_timeout),
        check_dependency(DependencyName.TASK_MANAGER_DB, task_manager_db_probe, timeout_seconds=check_timeout),
    )
    return list(checks)


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

        return await gather_dependency_health(
            database_probe=self._db.is_healthy,
            message_bus_probe=probe_message_bus,
            cache_probe=probe_cache,
            task_manager_probe=probe_workflow,
            task_manager_db_probe=self._task_manager_db_probe,
            check_timeout=self._check_timeout,
        )


async def probe_task_manager_db() -> bool:
    """Probe the task manager's backing store through the task manager's own readiness endpoint.

    The readiness endpoint reports whether the task manager can reach its database. Delegating the
    check to the task manager keeps the backing store's credentials out of this process: only the
    task manager authenticates to its own database, and a backing-store outage surfaces here as a
    non-success response.

    Raises:
        InitializationError: When the task manager API location is not configured. Without it the
            client would fall back to an in-process ephemeral server and report a meaningless UP.

    """
    if get_current_settings().api.url is None:
        raise InitializationError("Task manager API URL is not configured")

    # Disable client retries: a backing-store outage answers the readiness endpoint with a 503 that
    # the client would otherwise retry with exponential backoff, blocking the probe until the
    # health-check timeout cancels it. The probe must fail fast so the outage is reported promptly.
    with temporary_settings({PREFECT_CLIENT_MAX_RETRIES: 0}):
        async with get_client(sync_client=False) as client:
            response = await client._client.get("/ready")
            response.raise_for_status()
    return True
