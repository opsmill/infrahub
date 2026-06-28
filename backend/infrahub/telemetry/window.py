from datetime import UTC, datetime, timedelta

WINDOW_LENGTH = timedelta(hours=24)


def floor_to_midnight_utc(moment: datetime) -> datetime:
    """Return 00:00:00 UTC of the calendar day containing ``moment``."""
    in_utc = moment.astimezone(UTC)
    return in_utc.replace(hour=0, minute=0, second=0, microsecond=0)


def get_activity_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return the ``[window_start, window_end)`` covering the previous full UTC calendar day.

    ``window_end`` is midnight UTC of the current day and ``window_start`` is 24h earlier, so
    consecutive daily runs tile exactly regardless of when within the day they execute. The
    window is anchored to a deterministic calendar boundary, never to the raw ``now`` instant,
    which is what keeps a daily series free of overlaps and gaps.
    """
    reference = now if now is not None else datetime.now(tz=UTC)
    window_end = floor_to_midnight_utc(reference)
    window_start = window_end - WINDOW_LENGTH
    return window_start, window_end
