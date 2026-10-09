"""Unit tests for the per-worker resource share reported for each component.

A container's processes share its allocation, so one worker's share is the
container's figures divided by the processes that reported from it. The share
times the active workers is then the real total, whether a component runs one
process per container or several.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.telemetry.models import TelemetryPerWorkerData
from infrahub.telemetry.resources import WorkerResourceReading
from infrahub.telemetry.tasks import _per_worker_share


@dataclass
class ShareCase:
    name: str
    readings: list[WorkerResourceReading]
    expected: TelemetryPerWorkerData


SHARE_CASES = [
    ShareCase(
        name="one_process_per_container_keeps_the_container_figures",
        readings=[
            WorkerResourceReading(
                host=host,
                processor_available=4,
                processor_assigned=4,
                memory_total=8_000_000_000,
                memory_available=6_000_000_000,
            )
            for host in ("w1", "w2")
        ],
        expected=TelemetryPerWorkerData(
            processor_available=4.0,
            processor_assigned=4.0,
            memory_total=8_000_000_000,
            memory_available=6_000_000_000,
        ),
    ),
    ShareCase(
        name="processes_of_one_container_split_it_evenly",
        readings=[
            WorkerResourceReading(
                host="api",
                processor_available=4,
                processor_assigned=4,
                memory_total=8_000_000_000,
                memory_available=6_000_000_000,
            )
        ]
        * 4,
        expected=TelemetryPerWorkerData(
            processor_available=1.0,
            processor_assigned=1.0,
            memory_total=2_000_000_000,
            memory_available=1_500_000_000,
        ),
    ),
    ShareCase(
        name="an_uneven_split_rounds_processors_to_two_decimals",
        readings=[
            WorkerResourceReading(
                host="api",
                processor_available=4,
                processor_assigned=None,
                memory_total=8_000_000_000,
                memory_available=6_000_000_000,
            )
        ]
        * 3,
        expected=TelemetryPerWorkerData(
            processor_available=1.33,
            processor_assigned=None,
            memory_total=2_666_666_666,
            memory_available=2_000_000_000,
        ),
    ),
    ShareCase(
        name="more_processes_than_processors_gives_a_fraction",
        readings=[WorkerResourceReading(host="api", processor_available=2, processor_assigned=2)] * 4,
        expected=TelemetryPerWorkerData(processor_available=0.5, processor_assigned=0.5),
    ),
    ShareCase(
        name="a_failed_read_still_shares_its_container",
        readings=[
            *[WorkerResourceReading(host="api", processor_available=4, memory_total=8_000_000_000)] * 2,
            WorkerResourceReading.failed(host="api"),
        ],
        expected=TelemetryPerWorkerData(processor_available=1.33, memory_total=2_666_666_666),
    ),
    ShareCase(
        name="a_failed_read_from_another_container_does_not_change_the_share",
        readings=[
            *[WorkerResourceReading(host="api", processor_available=4, memory_total=8_000_000_000)] * 2,
            WorkerResourceReading.failed(host="other"),
        ],
        expected=TelemetryPerWorkerData(processor_available=2.0, memory_total=4_000_000_000),
    ),
    ShareCase(
        name="the_most_complete_reading_is_used_and_partial_ones_still_share",
        readings=[
            WorkerResourceReading(host="api", processor_available=4, memory_total=None),
            WorkerResourceReading(host="api", processor_available=4, memory_total=8_000_000_000),
        ],
        expected=TelemetryPerWorkerData(processor_available=2.0, memory_total=4_000_000_000),
    ),
    ShareCase(
        name="no_readings_reports_nothing",
        readings=[],
        expected=TelemetryPerWorkerData(),
    ),
    ShareCase(
        name="only_failed_reads_reports_nothing",
        readings=[WorkerResourceReading.failed(host="api"), WorkerResourceReading.failed(host="api")],
        expected=TelemetryPerWorkerData(),
    ),
]


@pytest.mark.parametrize("case", SHARE_CASES, ids=[case.name for case in SHARE_CASES])
def test_per_worker_share(case: ShareCase) -> None:
    assert _per_worker_share(case.readings) == case.expected
