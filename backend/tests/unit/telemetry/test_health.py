from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pytest

from infrahub.exceptions import InitializationError
from infrahub.health import (
    DependencyHealth,
    DependencyName,
    DependencyStatus,
    ErrorCategory,
    OverallStatus,
    gather_dependency_health,
)
from infrahub.telemetry.health import build_health_data, gather_health_data
from infrahub.telemetry.models import TelemetryHealthData
from tests.adapters.health import FailingProbe, HealthyProbe, SlowProbe, UnhealthyProbe


async def test_gather_dependency_health_all_up() -> None:
    checks = await gather_dependency_health(
        database_probe=HealthyProbe().is_healthy,
        message_bus_probe=HealthyProbe().is_healthy,
        cache_probe=HealthyProbe().is_healthy,
        task_manager_probe=HealthyProbe().is_healthy,
        task_manager_db_probe=HealthyProbe().is_healthy,
        check_timeout=3,
    )
    assert {c.name for c in checks} == set(DependencyName)
    assert all(c.status == DependencyStatus.UP for c in checks)
    assert all(c.error == ErrorCategory.NONE for c in checks)


async def test_gather_dependency_health_reports_each_failure_category() -> None:
    checks = await gather_dependency_health(
        database_probe=HealthyProbe().is_healthy,
        message_bus_probe=FailingProbe(ConnectionRefusedError()).is_healthy,
        cache_probe=UnhealthyProbe().is_healthy,
        task_manager_probe=HealthyProbe().is_healthy,
        task_manager_db_probe=FailingProbe(InitializationError("not configured")).is_healthy,
        check_timeout=3,
    )
    by_name = {c.name: c for c in checks}
    assert by_name[DependencyName.DATABASE].status == DependencyStatus.UP
    assert by_name[DependencyName.MESSAGE_BUS].status == DependencyStatus.DOWN
    assert by_name[DependencyName.MESSAGE_BUS].error == ErrorCategory.CONNECTION_REFUSED
    assert by_name[DependencyName.CACHE].status == DependencyStatus.DOWN
    assert by_name[DependencyName.CACHE].error == ErrorCategory.UNKNOWN_ERROR
    assert by_name[DependencyName.TASK_MANAGER].status == DependencyStatus.UP
    assert by_name[DependencyName.TASK_MANAGER_DB].status == DependencyStatus.DOWN
    assert by_name[DependencyName.TASK_MANAGER_DB].error == ErrorCategory.NOT_INITIALIZED


async def test_gather_dependency_health_reports_timeout() -> None:
    checks = await gather_dependency_health(
        database_probe=HealthyProbe().is_healthy,
        message_bus_probe=HealthyProbe().is_healthy,
        cache_probe=SlowProbe(delay=1).is_healthy,
        task_manager_probe=HealthyProbe().is_healthy,
        task_manager_db_probe=HealthyProbe().is_healthy,
        check_timeout=0.05,
    )
    by_name = {c.name: c for c in checks}
    assert by_name[DependencyName.CACHE].status == DependencyStatus.DOWN
    assert by_name[DependencyName.CACHE].error == ErrorCategory.TIMEOUT


@dataclass
class BuildStatusCase:
    name: str
    checks: list[DependencyHealth]
    expected: OverallStatus


BUILD_STATUS_CASES = [
    BuildStatusCase(
        name="all_up",
        checks=[
            DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.UP),
            DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.UP),
        ],
        expected=OverallStatus.HEALTHY,
    ),
    BuildStatusCase(
        name="one_down",
        checks=[
            DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.UP),
            DependencyHealth(name=DependencyName.CACHE, status=DependencyStatus.DOWN, error=ErrorCategory.TIMEOUT),
        ],
        expected=OverallStatus.UNHEALTHY,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in BUILD_STATUS_CASES])
def test_build_health_data(case: BuildStatusCase) -> None:
    result = build_health_data(case.checks)
    assert isinstance(result, TelemetryHealthData)
    assert result.status == case.expected
    assert result.checks == case.checks
    assert isinstance(result.timestamp, datetime)


async def test_gather_health_data_builds_snapshot() -> None:
    expected_checks = [
        DependencyHealth(name=DependencyName.DATABASE, status=DependencyStatus.UP),
        DependencyHealth(
            name=DependencyName.CACHE, status=DependencyStatus.DOWN, error=ErrorCategory.CONNECTION_CLOSED
        ),
    ]

    async def provider() -> list[DependencyHealth]:
        return expected_checks

    result = await gather_health_data(checks_provider=provider)
    assert result is not None
    assert result.status == OverallStatus.UNHEALTHY
    assert result.checks == expected_checks


async def test_gather_health_data_returns_none_when_gathering_fails() -> None:
    async def provider() -> list[DependencyHealth]:
        raise RuntimeError("collaborator could not be resolved")

    assert await gather_health_data(checks_provider=provider) is None


def test_health_snapshot_exposes_no_internal_details() -> None:
    checks = [
        DependencyHealth(
            name=DependencyName.TASK_MANAGER_DB, status=DependencyStatus.DOWN, error=ErrorCategory.CONNECTION_REFUSED
        ),
    ]
    snapshot = build_health_data(checks)
    json_str = snapshot.model_dump_json()
    for forbidden in ("localhost", "neo4j://", "redis://", "amqp://", "postgresql", "asyncpg", ":5432", "127.0.0.1"):
        assert forbidden not in json_str
    # The serialized error carries the categorized value, never free-form detail.
    serialized_errors = [check["error"] for check in snapshot.model_dump(mode="json")["checks"]]
    assert serialized_errors == [ErrorCategory.CONNECTION_REFUSED]
