from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from infrahub import config
from infrahub.health import DefaultHealthStatusEvaluator, gather_dependency_health
from infrahub.log import get_logger
from infrahub.workers.dependencies import (
    get_cache,
    get_database,
    get_message_bus,
    get_task_manager_db_probe,
    get_workflow,
)

from .models import TelemetryHealthData

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub.health import DependencyHealth

log = get_logger()


def build_health_data(checks: list[DependencyHealth]) -> TelemetryHealthData:
    """Aggregate per-dependency checks into the point-in-time telemetry health snapshot."""
    return TelemetryHealthData(
        status=DefaultHealthStatusEvaluator().evaluate(checks),
        checks=checks,
        timestamp=datetime.now(tz=UTC),
    )


async def _gather_checks() -> list[DependencyHealth]:
    # The four service collaborators are resolved inside their probe coroutines, so a
    # getter that raises is caught per dependency (reported DOWN) instead of nulling the
    # whole snapshot. The task-manager-DB probe is already a self-contained callable.
    async def database_probe() -> bool:
        return await (await get_database()).is_healthy()

    async def message_bus_probe() -> bool:
        return await (await get_message_bus()).is_healthy()

    async def cache_probe() -> bool:
        return await (await get_cache()).is_healthy()

    async def task_manager_probe() -> bool:
        return await get_workflow().is_healthy()

    return await gather_dependency_health(
        database_probe=database_probe,
        message_bus_probe=message_bus_probe,
        cache_probe=cache_probe,
        task_manager_probe=task_manager_probe,
        task_manager_db_probe=get_task_manager_db_probe(),
        check_timeout=config.SETTINGS.health.check_timeout,
    )


async def gather_health_data(
    checks_provider: Callable[[], Awaitable[list[DependencyHealth]]] = _gather_checks,
) -> TelemetryHealthData | None:
    """Point-in-time backing-service health for the anonymous telemetry payload.

    Returns None when the snapshot cannot be produced, so a health problem never
    prevents the rest of the telemetry payload from being recorded or sent.
    """
    try:
        checks = await checks_provider()
        return build_health_data(checks)
    except Exception as exc:
        log.warning("Unable to gather health data for telemetry", error=type(exc).__name__)
        return None
