from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from neo4j import READ_ACCESS, WRITE_ACCESS

from infrahub.database import InfrahubDatabase
from infrahub.execution_priority import bind_execution_priority
from infrahub.workflows.constants import WorkflowPriority

if TYPE_CHECKING:
    from neo4j import AsyncDriver


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
        name="read_session_of_another_priority", read_only=True, priority=WorkflowPriority.LOW, expected=READ_ACCESS
    ),
    AccessModeCase(
        name="read_session_outside_of_a_request_or_workflow", read_only=True, priority=None, expected=READ_ACCESS
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in ACCESS_MODE_CASES])
async def test_session_opens_with_the_access_mode_of_the_bound_priority(
    case: AccessModeCase, driver: AsyncDriver
) -> None:
    db = InfrahubDatabase(driver=driver, writer_read_priorities=frozenset({WorkflowPriority.HIGH}))

    with bind_execution_priority(case.priority):
        async with db.start_session(read_only=case.read_only) as dbs:
            session = await dbs.session()

    assert session._config.default_access_mode == case.expected
