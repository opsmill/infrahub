import importlib.metadata
import logging
from collections.abc import Awaitable

from .constants import InfrahubType

log = logging.getLogger(__name__)


def determine_infrahub_type() -> InfrahubType:
    try:
        importlib.metadata.version("infrahub-enterprise")
        return InfrahubType.ENTERPRISE
    except importlib.metadata.PackageNotFoundError:
        return InfrahubType.COMMUNITY


async def safe_metric[T](coro: Awaitable[T]) -> T | None:
    """Run one metric coroutine in isolation, degrading a failure to ``None``.

    Returns the awaited result on success — including a falsy value such as
    ``0`` (a source that succeeded with nothing to count). On any exception the
    failure is logged and ``None`` is returned, so a single broken source nulls
    only its own field instead of dropping the whole payload.
    """
    try:
        return await coro
    except Exception as exc:
        log.warning("Telemetry metric collection failed; reporting null for this field: %s", exc)
        return None
