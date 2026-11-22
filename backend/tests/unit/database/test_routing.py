from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from neo4j import READ_ACCESS, WRITE_ACCESS, AsyncDriver, AsyncGraphDatabase

from infrahub.config import DatabaseSettings
from infrahub.database import InfrahubDatabase, build_priority_read_routing
from infrahub.database.routing import (
    PriorityReadRouting,
    SessionRoute,
    bind_execution_priority,
    select_session_route,
)
from infrahub.workflows.constants import WorkflowPriority

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

UNREACHABLE_URI = "neo4j://127.0.0.1:9"


@pytest.fixture
async def default_driver() -> AsyncIterator[AsyncDriver]:
    driver = AsyncGraphDatabase.driver(UNREACHABLE_URI, auth=("neo4j", "unused"))
    yield driver
    await driver.close()


@pytest.fixture
async def low_driver() -> AsyncIterator[AsyncDriver]:
    driver = AsyncGraphDatabase.driver(f"{UNREACHABLE_URI}?policy=batch", auth=("neo4j", "unused"))
    yield driver
    await driver.close()


def build_routing(default_driver: AsyncDriver, low_driver: AsyncDriver) -> PriorityReadRouting:
    return PriorityReadRouting(
        routes={
            WorkflowPriority.LOW: SessionRoute(driver=low_driver, access_mode=READ_ACCESS),
            WorkflowPriority.HIGH: SessionRoute(driver=default_driver, access_mode=WRITE_ACCESS),
        },
        owned_drivers=[],
    )


@dataclass
class SessionRouteCase:
    name: str
    read_only: bool
    with_routing: bool
    priority: WorkflowPriority | None
    expected_on_low_driver: bool
    expected_access_mode: str


SESSION_ROUTE_CASES = [
    SessionRouteCase(
        name="write_session_ignores_the_route_of_its_priority",
        read_only=False,
        with_routing=True,
        priority=WorkflowPriority.LOW,
        expected_on_low_driver=False,
        expected_access_mode=WRITE_ACCESS,
    ),
    SessionRouteCase(
        name="read_session_without_routing",
        read_only=True,
        with_routing=False,
        priority=WorkflowPriority.LOW,
        expected_on_low_driver=False,
        expected_access_mode=READ_ACCESS,
    ),
    SessionRouteCase(
        name="read_session_outside_of_a_request_or_workflow",
        read_only=True,
        with_routing=True,
        priority=None,
        expected_on_low_driver=False,
        expected_access_mode=READ_ACCESS,
    ),
    SessionRouteCase(
        name="read_session_of_a_priority_without_a_route",
        read_only=True,
        with_routing=True,
        priority=WorkflowPriority.MEDIUM,
        expected_on_low_driver=False,
        expected_access_mode=READ_ACCESS,
    ),
    SessionRouteCase(
        name="read_session_of_a_priority_with_a_policy",
        read_only=True,
        with_routing=True,
        priority=WorkflowPriority.LOW,
        expected_on_low_driver=True,
        expected_access_mode=READ_ACCESS,
    ),
    SessionRouteCase(
        name="read_session_of_a_priority_that_reads_from_the_writer",
        read_only=True,
        with_routing=True,
        priority=WorkflowPriority.HIGH,
        expected_on_low_driver=False,
        expected_access_mode=WRITE_ACCESS,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in SESSION_ROUTE_CASES])
async def test_select_session_route(
    case: SessionRouteCase, default_driver: AsyncDriver, low_driver: AsyncDriver
) -> None:
    route = select_session_route(
        default_driver=default_driver,
        read_only=case.read_only,
        read_routing=build_routing(default_driver=default_driver, low_driver=low_driver) if case.with_routing else None,
        priority=case.priority,
    )

    expected_driver = low_driver if case.expected_on_low_driver else default_driver
    assert route == SessionRoute(driver=expected_driver, access_mode=case.expected_access_mode)


async def test_read_session_opens_on_the_route_of_the_bound_priority(
    default_driver: AsyncDriver, low_driver: AsyncDriver
) -> None:
    db = InfrahubDatabase(
        driver=default_driver, read_routing=build_routing(default_driver=default_driver, low_driver=low_driver)
    )

    with bind_execution_priority(WorkflowPriority.LOW):
        async with db.start_session(read_only=True) as dbs:
            session = await dbs.session()

    assert session._pool is low_driver._pool
    assert session._config.default_access_mode == READ_ACCESS


async def test_build_priority_read_routing_without_priority_settings(default_driver: AsyncDriver) -> None:
    settings = DatabaseSettings(protocol="neo4j", policy="batch")

    assert build_priority_read_routing(settings=settings, default_driver=default_driver) is None


async def test_build_priority_read_routing_opens_one_driver_per_policy(default_driver: AsyncDriver) -> None:
    settings = DatabaseSettings(
        protocol="neo4j",
        address="127.0.0.1:9",
        policy="default_readers",
        policy_high="interactive",
        policy_medium="interactive",
        policy_low="default_readers",
    )

    routing = build_priority_read_routing(settings=settings, default_driver=default_driver)
    assert routing is not None
    try:
        high_route = routing.route(priority=WorkflowPriority.HIGH)
        medium_route = routing.route(priority=WorkflowPriority.MEDIUM)
        low_route = routing.route(priority=WorkflowPriority.LOW)
        assert high_route is not None
        assert medium_route == high_route
        assert high_route.access_mode == READ_ACCESS
        assert high_route.driver is not default_driver
        assert low_route == SessionRoute(driver=default_driver, access_mode=READ_ACCESS)
    finally:
        await routing.close()


async def test_build_priority_read_routing_sends_writer_reads_to_the_writer(default_driver: AsyncDriver) -> None:
    settings = DatabaseSettings(protocol="neo4j", writer_read_priorities="high")

    routing = build_priority_read_routing(settings=settings, default_driver=default_driver)

    assert routing is not None
    assert routing.route(priority=WorkflowPriority.HIGH) == SessionRoute(
        driver=default_driver, access_mode=WRITE_ACCESS
    )
    assert routing.route(priority=WorkflowPriority.MEDIUM) is None
    assert routing.route(priority=WorkflowPriority.LOW) is None
