from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.query import QueryType
from infrahub.database import InfrahubDatabase, get_db, load_signal_registry
from infrahub.database.load_signal import ReferenceQueryLoadTracker
from infrahub.database.metrics import REFERENCE_QUERY_NAME
from infrahub.execution_priority import bind_execution_priority
from infrahub.workflows.constants import WorkflowPriority

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@dataclass
class SamplingCase:
    name: str
    read_only: bool
    priority: WorkflowPriority | None
    expected_samples: int


SAMPLING_CASES: list[SamplingCase] = [
    SamplingCase(
        name="read_session_of_a_writer_read_priority",
        read_only=True,
        priority=WorkflowPriority.HIGH,
        expected_samples=0,
    ),
    SamplingCase(
        name="read_session_of_another_priority",
        read_only=True,
        priority=WorkflowPriority.LOW,
        expected_samples=1,
    ),
    SamplingCase(
        name="read_session_outside_of_a_request_or_workflow",
        read_only=True,
        priority=None,
        expected_samples=1,
    ),
    SamplingCase(
        name="write_session_of_a_writer_read_priority",
        read_only=False,
        priority=WorkflowPriority.HIGH,
        expected_samples=1,
    ),
]


@pytest.fixture
async def high_reads_on_writer_db(db: InfrahubDatabase) -> AsyncGenerator[InfrahubDatabase]:
    driver = await get_db()
    yield InfrahubDatabase(driver=driver, writer_read_priorities=frozenset({WorkflowPriority.HIGH}))
    await driver.close()


@pytest.fixture
def stress_tracker(monkeypatch: pytest.MonkeyPatch) -> ReferenceQueryLoadTracker:
    # A clock that never advances keeps every sample inside the window.
    tracker = ReferenceQueryLoadTracker(observers=[], clock=lambda: 0.0)
    monkeypatch.setattr(load_signal_registry, "_reference_query_load_tracker", tracker)
    return tracker


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in SAMPLING_CASES])
async def test_reference_query_feeds_the_stress_signal_unless_its_priority_reads_on_the_writer(
    case: SamplingCase, high_reads_on_writer_db: InfrahubDatabase, stress_tracker: ReferenceQueryLoadTracker
) -> None:
    with bind_execution_priority(case.priority):
        async with high_reads_on_writer_db.start_session(read_only=case.read_only) as dbs:
            await dbs.execute_query(query="RETURN 1", name=REFERENCE_QUERY_NAME, type=QueryType.READ)

    assert stress_tracker.sample_count() == case.expected_samples
