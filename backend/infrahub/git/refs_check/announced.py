"""Recording the remote head the worker pool has been told about on one Infrahub branch."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.git.state.cache_keys import REFS_CHECK_ANNOUNCED_TTL_SECONDS, refs_check_announced_key
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.services.adapters.cache import InfrahubCache

log = get_logger()


async def record_announced_head(
    *, cache: InfrahubCache, repository_id: str, repository_name: str, branch_name: str, head: str
) -> None:
    """Remember that the pool has been told about ``head`` on one branch, best effort.

    Call it only once the broadcast naming ``head`` has been sent: a value written earlier would
    stop the refs check from retrying a broadcast that never went out. Never raises: a value that
    could not be written costs one repeated broadcast on a later check, which every recipient
    absorbs by resetting to the commit it already holds.
    """
    try:
        await cache.set(
            key=refs_check_announced_key(repository_id, branch_name),
            value=head,
            expires=REFS_CHECK_ANNOUNCED_TTL_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "Could not record the announced head",
            repository=repository_name,
            branch=branch_name,
            reason=str(exc),
        )
