import importlib.metadata
from collections.abc import Awaitable
from datetime import UTC, datetime, timedelta

from infrahub.log import get_run_logger

from .constants import InfrahubType

log = get_run_logger()

WINDOW_LENGTH = timedelta(hours=24)


def determine_infrahub_type() -> InfrahubType:
    try:
        importlib.metadata.version("infrahub-enterprise")
        return InfrahubType.ENTERPRISE
    except importlib.metadata.PackageNotFoundError:
        return InfrahubType.COMMUNITY


async def safe_metric[T](coro: Awaitable[T]) -> T | None:
    """Await ``coro`` and return its result, or ``None`` if it raises (the error is logged).

    A falsy result such as ``0`` is returned as-is; only an exception maps to ``None``.
    """
    try:
        return await coro
    # Degradation boundary: any collection failure must null out one field, never fail the whole telemetry run
    except Exception as exc:  # noqa: BLE001
        log.warning("Telemetry metric collection failed; reporting null for this field: %s", exc)
        return None


def floor_to_midnight_utc(moment: datetime) -> datetime:
    """Return 00:00:00 UTC of the calendar day containing ``moment``."""
    in_utc = moment.astimezone(UTC)
    return in_utc.replace(hour=0, minute=0, second=0, microsecond=0)


def get_activity_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return the half-open ``[window_start, window_end)`` for the previous full UTC day."""
    reference = now if now is not None else datetime.now(tz=UTC)
    window_end = floor_to_midnight_utc(reference)
    window_start = window_end - WINDOW_LENGTH
    return window_start, window_end


def inclusive_end(window_end: datetime) -> datetime:
    """Return the last instant inside the half-open window: ``window_end`` minus one microsecond."""
    return window_end - timedelta(microseconds=1)
