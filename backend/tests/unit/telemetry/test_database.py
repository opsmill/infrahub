"""Unit tests for interpreting the raw Cypher-parallelism worker-limit setting.

The setting defaults to ``0`` (auto = unbounded), which is not an enforced limit
and maps to ``None``; a positive integer is the configured core cap. An absent,
non-numeric, or non-positive value is also reported as no configured limit.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.telemetry.database import _worker_limit_from_value


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
    WorkerLimitCase(name="empty_string", value="", expected=None),
    WorkerLimitCase(name="none", value=None, expected=None),
]


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_worker_limit_from_value(case: WorkerLimitCase) -> None:
    assert _worker_limit_from_value(case.value) == case.expected
