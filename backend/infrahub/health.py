from __future__ import annotations

import asyncio
import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel

from infrahub.exceptions import DependencyConnectionClosedError, DependencyUnhealthyError
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterator


log = get_logger()

HEALTH_REPORT_MAX_AGE_SECONDS = 1.0
"""How long one round of checks answers later requests, so callers of the unauthenticated endpoint cannot
multiply the load on the backing services."""


class DependencyName(StrEnum):
    DATABASE = "database"
    MESSAGE_BUS = "message_bus"
    CACHE = "cache"
    TASK_MANAGER = "task_manager"
    TASK_MANAGER_DB = "task_manager_db"


class DependencyStatus(StrEnum):
    UP = "up"
    DOWN = "down"


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class ErrorCategory(StrEnum):
    """Why a dependency is down, without the internal details an unauthenticated caller must not see."""

    NONE = "none"
    TIMEOUT = "timeout"
    CONNECTION_REFUSED = "connection_refused"
    CONNECTION_CLOSED = "connection_closed"
    NAME_RESOLUTION_FAILED = "name_resolution_failed"
    UNAVAILABLE = "unavailable"
    """The service answered but reported that it cannot serve requests."""
    UNKNOWN_ERROR = "unknown_error"


class DependencyHealth(BaseModel):
    name: DependencyName
    status: DependencyStatus
    error: ErrorCategory = ErrorCategory.NONE


class HealthReport(BaseModel):
    status: HealthStatus
    dependencies: list[DependencyHealth]
    timestamp: datetime
    """When the checks behind this report ran."""


class SupportsHealthCheck(Protocol):
    async def check_health(self) -> None: ...


class SupportsTaskManagerHealthCheck(SupportsHealthCheck, Protocol):
    async def check_database_health(self) -> None: ...


@dataclass(frozen=True)
class DependencyCheck:
    name: DependencyName
    check: Callable[[], Awaitable[None]]
    """Returns when the dependency is healthy and raises otherwise."""


def classify_error(exc: BaseException) -> ErrorCategory:
    """Return the category of the first exception in the chain that has one, from the outermost inwards."""
    for error in _exception_chain(exc):
        category = _category_of(error)
        if category is not None:
            return category
    return ErrorCategory.UNKNOWN_ERROR


def _exception_chain(exc: BaseException) -> Iterator[BaseException]:
    # The members of an exception group come before its cause: a client that tries every address of a name raises one.
    seen: set[int] = set()
    pending: list[BaseException] = [exc]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        following = [current.__cause__ or current.__context__]
        if isinstance(current, BaseExceptionGroup):
            following = [*current.exceptions, *following]
        pending.extend(reversed([error for error in following if error is not None]))


def _category_of(error: BaseException) -> ErrorCategory | None:
    match error:
        case TimeoutError():
            return ErrorCategory.TIMEOUT
        case socket.gaierror():
            return ErrorCategory.NAME_RESOLUTION_FAILED
        case ConnectionRefusedError():
            return ErrorCategory.CONNECTION_REFUSED
        case ConnectionResetError() | ConnectionAbortedError() | BrokenPipeError() | DependencyConnectionClosedError():
            return ErrorCategory.CONNECTION_CLOSED
        case DependencyUnhealthyError():
            return ErrorCategory.UNAVAILABLE
    return None


class HealthChecker:
    """Checks the backing services concurrently and reports whether this API server can serve requests."""

    def __init__(
        self,
        checks: list[DependencyCheck],
        check_timeout: float,
        max_report_age: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._checks = checks
        self._check_timeout = check_timeout
        self._max_report_age = max_report_age
        self._clock = clock
        self._lock = asyncio.Lock()
        self._latest: tuple[float, HealthReport] | None = None

    async def report(self) -> HealthReport:
        """Run every check, or return the report of a round that ended less than the maximum age ago.

        Concurrent callers wait for the round in progress instead of starting their own.
        """
        async with self._lock:
            if self._latest is not None:
                ended_at, latest = self._latest
                if self._clock() - ended_at < self._max_report_age:
                    return latest

            dependencies = list(await asyncio.gather(*(self._run_check(check) for check in self._checks)))
            healthy = all(dependency.status == DependencyStatus.UP for dependency in dependencies)
            report = HealthReport(
                status=HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY,
                dependencies=dependencies,
                timestamp=datetime.now(tz=UTC),
            )
            self._latest = (self._clock(), report)
            return report

    async def _run_check(self, dependency: DependencyCheck) -> DependencyHealth:
        try:
            async with asyncio.timeout(self._check_timeout):
                await dependency.check()
        # Each failed check becomes a DOWN entry in the report instead of failing the other checks.
        except Exception as exc:  # noqa: BLE001
            error = classify_error(exc)
            log.warning(
                "Health check failed",
                dependency=dependency.name.value,
                error_category=error.value,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return DependencyHealth(name=dependency.name, status=DependencyStatus.DOWN, error=error)
        return DependencyHealth(name=dependency.name, status=DependencyStatus.UP)


def build_health_checker(
    database: SupportsHealthCheck,
    message_bus: SupportsHealthCheck,
    cache: SupportsHealthCheck,
    workflow: SupportsTaskManagerHealthCheck,
    check_timeout: float,
) -> HealthChecker:
    return HealthChecker(
        checks=[
            DependencyCheck(name=DependencyName.DATABASE, check=database.check_health),
            DependencyCheck(name=DependencyName.MESSAGE_BUS, check=message_bus.check_health),
            DependencyCheck(name=DependencyName.CACHE, check=cache.check_health),
            DependencyCheck(name=DependencyName.TASK_MANAGER, check=workflow.check_health),
            DependencyCheck(name=DependencyName.TASK_MANAGER_DB, check=workflow.check_database_health),
        ],
        check_timeout=check_timeout,
        max_report_age=HEALTH_REPORT_MAX_AGE_SECONDS,
    )
