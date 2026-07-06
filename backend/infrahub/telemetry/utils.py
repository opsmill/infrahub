import importlib.metadata
from collections.abc import Awaitable

from infrahub.log import get_run_logger

from .constants import InfrahubType

log = get_run_logger()


def determine_infrahub_type() -> InfrahubType:
    try:
        importlib.metadata.version("infrahub-enterprise")
        return InfrahubType.ENTERPRISE
    except importlib.metadata.PackageNotFoundError:
        return InfrahubType.COMMUNITY


async def safe_metric[T](coro: Awaitable[T]) -> T | None:
    """Run one metric coroutine in isolation, degrading a failure to ``None``.

    A falsy result like ``0`` is preserved (measured, nothing to count); only an exception
    yields ``None`` (logged), so one broken source nulls its own field, not the whole payload.
    """
    try:
        return await coro
    except Exception as exc:
        log.warning("Telemetry metric collection failed; reporting null for this field: %s", exc)
        return None
