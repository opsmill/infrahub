from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from neo4j import READ_ACCESS, WRITE_ACCESS, AsyncDriver, AsyncGraphDatabase

from infrahub.database import InfrahubDatabase
from infrahub.database.routing import bind_execution_priority, session_access_mode
from infrahub.workflows.constants import WorkflowPriority

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

WRITER_READ_PRIORITIES = frozenset({WorkflowPriority.HIGH})


@pytest.fixture
async def driver() -> AsyncIterator[AsyncDriver]:
    driver = AsyncGraphDatabase.driver("neo4j://127.0.0.1:9", auth=("neo4j", "unused"))
    yield driver
    await driver.close()


@dataclass
class AccessModeCase:
    name: str
    read_only: bool
    priority: WorkflowPriority | None
    expected: str


ACCESS_MODE_CASES = [
    AccessModeCase(name="write_session", read_only=False, priority=WorkflowPriority.LOW, expected=WRITE_ACCESS),
    AccessModeCase(
        name="read_session_of_a_writer_read_priority",
        read_only=True,
        priority=WorkflowPriority.HIGH,
        expected=WRITE_ACCESS,
    ),
    AccessModeCase(
        name="read_session_of_another_priority", read_only=True, priority=WorkflowPriority.MEDIUM, expected=READ_ACCESS
    ),
    AccessModeCase(
        name="read_session_outside_of_a_request_or_workflow", read_only=True, priority=None, expected=READ_ACCESS
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in ACCESS_MODE_CASES])
def test_session_access_mode(case: AccessModeCase) -> None:
    access_mode = session_access_mode(
        read_only=case.read_only, priority=case.priority, writer_read_priorities=WRITER_READ_PRIORITIES
    )

    assert access_mode == case.expected


@dataclass
class OpenedSessionCase:
    name: str
    priority: WorkflowPriority
    expected: str


OPENED_SESSION_CASES = [
    OpenedSessionCase(name="writer_read_priority", priority=WorkflowPriority.HIGH, expected=WRITE_ACCESS),
    OpenedSessionCase(name="other_priority", priority=WorkflowPriority.LOW, expected=READ_ACCESS),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in OPENED_SESSION_CASES])
async def test_read_session_opens_with_the_access_mode_of_the_bound_priority(
    case: OpenedSessionCase, driver: AsyncDriver
) -> None:
    db = InfrahubDatabase(driver=driver, writer_read_priorities=WRITER_READ_PRIORITIES)

    with bind_execution_priority(case.priority):
        async with db.start_session(read_only=True) as dbs:
            session = await dbs.session()

    assert session._config.default_access_mode == case.expected
