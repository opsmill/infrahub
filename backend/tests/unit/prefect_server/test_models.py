from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pytest

from infrahub.prefect_server.models import default_range


@dataclass
class DefaultRangeTestCase:
    name: str
    event_retention: timedelta
    expected: timedelta


DEFAULT_RANGE_TEST_CASES: list[DefaultRangeTestCase] = [
    DefaultRangeTestCase(
        name="retention_shorter_than_180_days", event_retention=timedelta(days=7), expected=timedelta(days=180)
    ),
    DefaultRangeTestCase(
        name="retention_of_180_days", event_retention=timedelta(days=180), expected=timedelta(days=180)
    ),
    DefaultRangeTestCase(
        name="retention_longer_than_180_days", event_retention=timedelta(days=365), expected=timedelta(days=365)
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in DEFAULT_RANGE_TEST_CASES])
def test_default_range_is_the_event_retention_and_at_least_180_days(test_case: DefaultRangeTestCase) -> None:
    assert default_range(event_retention=test_case.event_retention) == test_case.expected
