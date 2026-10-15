"""Unit tests for interpreting the raw Neo4j setting values the database telemetry reads.

The Cypher-parallelism worker limit defaults to ``0`` (auto = unbounded), which is not
an enforced limit and maps to ``None``; a positive integer is the configured core cap.
The heap and page cache sizes come back as text rounded to two decimals in a binary
unit, and count only when both are set.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.telemetry.database import _memory_assigned_from_values, _worker_limit_from_value


@dataclass
class WorkerLimitCase:
    name: str
    value: object
    expected: int | None


CASES = [
    WorkerLimitCase(name="positive_string", value="300", expected=300),
    WorkerLimitCase(name="positive_int", value=300, expected=300),
    WorkerLimitCase(name="auto_zero", value="0", expected=None),
    WorkerLimitCase(name="negative", value="-1", expected=None),
    WorkerLimitCase(name="non_numeric", value="abc", expected=None),
    WorkerLimitCase(name="none", value=None, expected=None),
]


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_worker_limit_from_value(case: WorkerLimitCase) -> None:
    assert _worker_limit_from_value(case.value) == case.expected


@dataclass
class MemoryAssignedCase:
    name: str
    heap_max: object
    pagecache: object
    expected: int | None


MEMORY_CASES = [
    MemoryAssignedCase(name="both_set", heap_max="1.00GiB", pagecache="512.00MiB", expected=1_610_612_736),
    MemoryAssignedCase(name="large_preset", heap_max="31.00GiB", pagecache="16.00GiB", expected=50_465_865_728),
    MemoryAssignedCase(name="rounded_values", heap_max="1.46GiB", pagecache="292.97MiB", expected=1_874_864_374),
    MemoryAssignedCase(name="plain_bytes", heap_max="1024", pagecache="2048B", expected=3_072),
    MemoryAssignedCase(name="heap_unset", heap_max=None, pagecache="512.00MiB", expected=None),
    MemoryAssignedCase(name="pagecache_unset", heap_max="1.00GiB", pagecache=None, expected=None),
    MemoryAssignedCase(name="non_numeric", heap_max="abc", pagecache="512.00MiB", expected=None),
    MemoryAssignedCase(name="unknown_unit", heap_max="1.00GB", pagecache="512.00MiB", expected=None),
    MemoryAssignedCase(name="not_text", heap_max=1_073_741_824, pagecache="512.00MiB", expected=None),
]


@pytest.mark.parametrize("case", MEMORY_CASES, ids=[case.name for case in MEMORY_CASES])
def test_memory_assigned_from_values(case: MemoryAssignedCase) -> None:
    assert _memory_assigned_from_values(case.heap_max, case.pagecache) == case.expected
