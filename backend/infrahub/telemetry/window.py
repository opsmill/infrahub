from datetime import UTC, datetime, timedelta

WINDOW_LENGTH = timedelta(hours=24)


def floor_to_midnight_utc(moment: datetime) -> datetime:
    """Return 00:00:00 UTC of the calendar day containing ``moment``."""
    in_utc = moment.astimezone(UTC)
    return in_utc.replace(hour=0, minute=0, second=0, microsecond=0)


def get_activity_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return the half-open ``[window_start, window_end)`` for the previous full UTC day.

    Anchored to the midnight-UTC boundary, not the raw ``now`` instant, so consecutive daily
    runs tile exactly — no overlaps or gaps — whatever time the (jittered) cron fires.
    """
    reference = now if now is not None else datetime.now(tz=UTC)
    window_end = floor_to_midnight_utc(reference)
    window_start = window_end - WINDOW_LENGTH
    return window_start, window_end


def inclusive_end(window_end: datetime) -> datetime:
    """The last instant inside the half-open ``[window_start, window_end)`` window.

    ``window_end`` itself is excluded; at microsecond resolution the last included instant is one
    microsecond earlier. Query APIs whose upper bound is inclusive ("at or before") need this so
    a record on the boundary lands in exactly one day's window, never two.
    """
    return window_end - timedelta(microseconds=1)
