from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.services.adapters.cache import InfrahubCache

# The sweep clears a marker once its re-point is reconciled; this only removes one that never is.
RETARGET_MARKER_TTL_SECONDS = 7 * 24 * 60 * 60


class RetargetMarkers:
    """Marks an Infrahub branch whose repository was re-pointed on purpose, so a sync does not report it as a rewrite.

    A marker names the git branch that feeds the Infrahub branch after the change. It applies only to a sync
    that reads that same git branch, so a sync that started before the change neither uses it nor deletes it.
    """

    def __init__(self, cache: InfrahubCache) -> None:
        self.cache = cache

    async def mark(self, repository_id: str, infrahub_branch_name: str, target: str) -> None:
        """Mark the branch as re-pointed at the git branch ``target``, for seven days at most."""
        await self.cache.set(
            key=self._key(repository_id=repository_id, infrahub_branch_name=infrahub_branch_name),
            value=target,
            expires=RETARGET_MARKER_TTL_SECONDS,
        )

    async def is_retargeted(self, repository_id: str, infrahub_branch_name: str, target: str) -> bool:
        """Whether the branch carries a marker that names ``target``. The marker stays in place."""
        key = self._key(repository_id=repository_id, infrahub_branch_name=infrahub_branch_name)
        return await self.cache.get(key=key) == target

    async def clear(self, repository_id: str, infrahub_branch_name: str, target: str) -> None:
        """Delete the marker of the branch when it names ``target``, and leave a marker for another target."""
        key = self._key(repository_id=repository_id, infrahub_branch_name=infrahub_branch_name)
        if await self.cache.get(key=key) == target:
            await self.cache.delete(key=key)

    @staticmethod
    def _key(repository_id: str, infrahub_branch_name: str) -> str:
        return f"git_retarget:{repository_id}:{infrahub_branch_name}"
