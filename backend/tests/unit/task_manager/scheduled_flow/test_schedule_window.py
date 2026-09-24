from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from infrahub.task_manager.scheduled_flow.schedule_window import interval_seconds, next_fire_times

NOW = datetime(2026, 9, 24, 7, 30, 15, tzinfo=UTC)


@dataclass
class IntervalCase:
    name: str
    cron: str
    expected: int | None


INTERVAL_CASES = [
    IntervalCase(name="every_minute", cron="* * * * *", expected=60),
    IntervalCase(name="daily_at_0217", cron="17 2 * * *", expected=86400),
    IntervalCase(name="daily_at_0342", cron="42 3 * * *", expected=86400),
    IntervalCase(name="every_six_hours", cron="0 */6 * * *", expected=21600),
    IntervalCase(name="uninterpretable_cron", cron="not a cron", expected=None),
]


@pytest.mark.parametrize("case", INTERVAL_CASES, ids=[c.name for c in INTERVAL_CASES])
async def test_interval_seconds(case: IntervalCase) -> None:
    assert await interval_seconds(cron=case.cron, start=NOW) == case.expected


@dataclass
class FireTimeCase:
    name: str
    cron: str
    expected_first: datetime


FIRE_TIME_CASES = [
    FireTimeCase(name="every_minute", cron="* * * * *", expected_first=datetime(2026, 9, 24, 7, 31, tzinfo=UTC)),
    FireTimeCase(name="daily_at_0217", cron="17 2 * * *", expected_first=datetime(2026, 9, 25, 2, 17, tzinfo=UTC)),
    FireTimeCase(name="daily_at_0342", cron="42 3 * * *", expected_first=datetime(2026, 9, 25, 3, 42, tzinfo=UTC)),
]


@pytest.mark.parametrize("case", FIRE_TIME_CASES, ids=[c.name for c in FIRE_TIME_CASES])
async def test_next_fire_times_are_in_the_future(case: FireTimeCase) -> None:
    dates = await next_fire_times(cron=case.cron, start=NOW, count=1)

    assert len(dates) == 1
    assert dates[0] == case.expected_first
    assert dates[0] > NOW


async def test_uninterpretable_cron_returns_no_fire_times_rather_than_raising() -> None:
    assert await next_fire_times(cron="not a cron", start=NOW, count=2) == []
