from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

import pytest

from infrahub.prefect_server.database import earlier_by, newest_first_ranges

FIVE_HOURS_EAST = timezone(timedelta(hours=5))
FIVE_HOURS_WEST = timezone(timedelta(hours=-5))
UNTIL = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


@dataclass
class EarlierByTestCase:
    name: str
    moment: datetime
    duration: timedelta
    expected: datetime


EARLIER_BY_TEST_CASES: list[EarlierByTestCase] = [
    EarlierByTestCase(
        name="recent_time",
        moment=datetime(2026, 10, 28, tzinfo=UTC),
        duration=timedelta(days=7),
        expected=datetime(2026, 10, 21, tzinfo=UTC),
    ),
    EarlierByTestCase(
        name="one_minute_after_the_earliest_datetime",
        moment=datetime(1, 1, 8, 0, 1, tzinfo=UTC),
        duration=timedelta(days=7),
        expected=datetime(1, 1, 1, 0, 1, tzinfo=UTC),
    ),
    EarlierByTestCase(
        name="exactly_the_earliest_datetime",
        moment=datetime(1, 1, 8, tzinfo=UTC),
        duration=timedelta(days=7),
        expected=datetime(1, 1, 1, tzinfo=UTC),
    ),
    EarlierByTestCase(
        name="before_year_1",
        moment=datetime(1, 1, 2, tzinfo=UTC),
        duration=timedelta(days=7),
        expected=datetime(1, 1, 1, tzinfo=UTC),
    ),
    EarlierByTestCase(
        name="duration_longer_than_the_datetime_range",
        moment=datetime(2026, 10, 28, tzinfo=UTC),
        duration=timedelta(days=800_000),
        expected=datetime(1, 1, 1, tzinfo=UTC),
    ),
    EarlierByTestCase(
        name="recent_time_east_of_utc",
        moment=datetime(2026, 10, 28, tzinfo=FIVE_HOURS_EAST),
        duration=timedelta(days=7),
        expected=datetime(2026, 10, 20, 19, tzinfo=UTC),
    ),
    EarlierByTestCase(
        name="before_year_1_in_utc_east_of_utc",
        moment=datetime(1, 1, 1, 6, tzinfo=FIVE_HOURS_EAST),
        duration=timedelta(hours=2),
        expected=datetime(1, 1, 1, tzinfo=UTC),
    ),
    EarlierByTestCase(
        name="before_year_1_in_local_time_west_of_utc",
        moment=datetime(1, 1, 1, 3, tzinfo=FIVE_HOURS_WEST),
        duration=timedelta(hours=7),
        expected=datetime(1, 1, 1, 1, tzinfo=UTC),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in EARLIER_BY_TEST_CASES])
def test_a_time_before_year_1_becomes_the_earliest_utc_datetime(test_case: EarlierByTestCase) -> None:
    """The time before a moment is returned in UTC, and a time before year 1 in UTC becomes the earliest datetime."""
    result = earlier_by(moment=test_case.moment, duration=test_case.duration)

    assert result == test_case.expected
    assert result.tzinfo is UTC


@dataclass
class NewestFirstRangesTestCase:
    name: str
    since: datetime
    expected: list[tuple[datetime, datetime]]
    until: datetime = UNTIL


NEWEST_FIRST_RANGES_TEST_CASES: list[NewestFirstRangesTestCase] = [
    NewestFirstRangesTestCase(
        name="start_before_every_window",
        since=datetime(2025, 10, 28, 12, 0, tzinfo=UTC),
        expected=[
            (datetime(2026, 10, 28, 11, 0, tzinfo=UTC), UNTIL),
            (datetime(2026, 10, 27, 12, 0, tzinfo=UTC), datetime(2026, 10, 28, 10, 59, 59, 999999, tzinfo=UTC)),
            (datetime(2026, 10, 21, 12, 0, tzinfo=UTC), datetime(2026, 10, 27, 11, 59, 59, 999999, tzinfo=UTC)),
            (datetime(2026, 9, 28, 12, 0, tzinfo=UTC), datetime(2026, 10, 21, 11, 59, 59, 999999, tzinfo=UTC)),
            (datetime(2025, 10, 28, 12, 0, tzinfo=UTC), datetime(2026, 9, 28, 11, 59, 59, 999999, tzinfo=UTC)),
        ],
    ),
    NewestFirstRangesTestCase(
        name="start_on_the_start_of_a_window",
        since=datetime(2026, 10, 21, 12, 0, tzinfo=UTC),
        expected=[
            (datetime(2026, 10, 28, 11, 0, tzinfo=UTC), UNTIL),
            (datetime(2026, 10, 27, 12, 0, tzinfo=UTC), datetime(2026, 10, 28, 10, 59, 59, 999999, tzinfo=UTC)),
            (datetime(2026, 10, 21, 12, 0, tzinfo=UTC), datetime(2026, 10, 27, 11, 59, 59, 999999, tzinfo=UTC)),
        ],
    ),
    NewestFirstRangesTestCase(
        name="start_inside_the_first_day",
        since=datetime(2026, 10, 28, 10, 0, tzinfo=UTC),
        expected=[
            (datetime(2026, 10, 28, 11, 0, tzinfo=UTC), UNTIL),
            (datetime(2026, 10, 28, 10, 0, tzinfo=UTC), datetime(2026, 10, 28, 10, 59, 59, 999999, tzinfo=UTC)),
        ],
    ),
    NewestFirstRangesTestCase(
        name="start_inside_the_first_hour",
        since=datetime(2026, 10, 28, 11, 30, tzinfo=UTC),
        expected=[(datetime(2026, 10, 28, 11, 30, tzinfo=UTC), UNTIL)],
    ),
    NewestFirstRangesTestCase(
        name="range_at_the_earliest_datetime",
        since=datetime(1, 1, 1, tzinfo=UTC),
        until=datetime(1, 1, 1, 0, 30, tzinfo=UTC),
        expected=[(datetime(1, 1, 1, tzinfo=UTC), datetime(1, 1, 1, 0, 30, tzinfo=UTC))],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in NEWEST_FIRST_RANGES_TEST_CASES])
def test_the_windows_split_the_range_without_overlap(test_case: NewestFirstRangesTestCase) -> None:
    """The windows cover the range newest first, each ending one microsecond before the newer one starts."""
    assert newest_first_ranges(since=test_case.since, until=test_case.until) == test_case.expected
