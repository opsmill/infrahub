"""Unit tests for the CPU and memory figures reported for each component.

Each block counts the component's processes and reports one of its containers
undivided, with how many processes share that container, so the component's
total is the container's figures times the active processes divided by the
processes per container.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.services.component import WorkerInfo
from infrahub.telemetry.models import TelemetryComponentData, TelemetryContainerData
from infrahub.telemetry.resources import WorkerResourceReading
from infrahub.telemetry.tasks import _component_data


def _workers(active: int, inactive: int = 0) -> list[WorkerInfo]:
    workers = []
    for index in range(active + inactive):
        worker = WorkerInfo(identity=f"w{index}")
        worker.active = index < active
        workers.append(worker)
    return workers


API_CONTAINER = WorkerResourceReading(
    processes_per_container=3,
    processor_available=6,
    processor_assigned=6,
    memory_total=12_000_000_000,
    memory_available=9_000_000_000,
)


@dataclass
class ComponentCase:
    name: str
    workers: list[WorkerInfo]
    readings: list[WorkerResourceReading]
    expected: TelemetryComponentData


COMPONENT_CASES = [
    ComponentCase(
        name="a_shared_container_is_reported_whole_with_its_process_count",
        workers=_workers(active=3),
        readings=[API_CONTAINER] * 3,
        expected=TelemetryComponentData(
            total=3,
            active=3,
            processes_per_container=3,
            per_container=TelemetryContainerData(
                processor_available=6,
                processor_assigned=6,
                memory_total=12_000_000_000,
                memory_available=9_000_000_000,
            ),
        ),
    ),
    ComponentCase(
        name="the_most_complete_reading_is_used",
        workers=_workers(active=2),
        readings=[
            WorkerResourceReading(processes_per_container=1, processor_available=4),
            WorkerResourceReading(processes_per_container=1, processor_available=4, memory_total=8_000_000_000),
        ],
        expected=TelemetryComponentData(
            total=2,
            active=2,
            processes_per_container=1,
            per_container=TelemetryContainerData(processor_available=4, memory_total=8_000_000_000),
        ),
    ),
    ComponentCase(
        name="a_reading_without_figures_still_gives_the_process_count",
        workers=_workers(active=1),
        readings=[WorkerResourceReading(processes_per_container=1)],
        expected=TelemetryComponentData(total=1, active=1, processes_per_container=1),
    ),
    ComponentCase(
        name="no_reading_leaves_the_figures_and_the_process_count_unknown",
        workers=_workers(active=1, inactive=1),
        readings=[],
        expected=TelemetryComponentData(total=2, active=1),
    ),
]


@pytest.mark.parametrize("case", COMPONENT_CASES, ids=[case.name for case in COMPONENT_CASES])
def test_component_data(case: ComponentCase) -> None:
    assert _component_data(case.workers, case.readings) == case.expected
