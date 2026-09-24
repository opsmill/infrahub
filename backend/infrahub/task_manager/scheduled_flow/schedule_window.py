"""Cron interpretation for scheduled deployments.

This is the only module in the feature that imports `prefect.server.schemas.schedules`: the
client-side `CronSchedule` has no way to compute fire times, so a Prefect upgrade that moves or
renames that API has exactly one place to fix.
"""

from datetime import datetime

from prefect.server.schemas.schedules import CronSchedule
from pydantic import ValidationError

from infrahub.log import get_logger

log = get_logger()


async def next_fire_times(cron: str, start: datetime, count: int, timezone: str | None = None) -> list[datetime]:
    """Return the next fire times for a cron expression, or an empty list if it cannot be interpreted."""
    try:
        schedule = CronSchedule(cron=cron, timezone=timezone) if timezone else CronSchedule(cron=cron)
        return list(await schedule.get_dates(n=count, start=start))
    except (ValidationError, ValueError) as exc:
        log.info(f"Unable to interpret the cron expression '{cron}': {exc}")
        return []


async def interval_seconds(cron: str, start: datetime, timezone: str | None = None) -> int | None:
    """Return the gap between the next two fire times, or None when the cron cannot be interpreted."""
    dates = await next_fire_times(cron=cron, start=start, count=2, timezone=timezone)
    if len(dates) < 2:
        return None
    return int((dates[1] - dates[0]).total_seconds())
