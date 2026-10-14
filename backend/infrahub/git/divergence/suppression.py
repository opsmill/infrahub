from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.services.adapters.cache import InfrahubCache

# The sweep clears a marker once its re-point is reconciled; this only removes one that never is.
RETARGET_MARKER_TTL_SECONDS = 7 * 24 * 60 * 60


class RetargetMarkers:
    """Marks a repository whose default branch was re-pointed on purpose, so a sync does not report it as a rewrite.

    Each marker names one git branch, the new default branch, and applies only to a sync that reads that same
    git branch. A marker for one target never replaces or deletes the marker for another.
    """

    def __init__(self, cache: InfrahubCache) -> None:
        self.cache = cache

    async def mark(self, repository_id: str, target: str) -> None:
        """Mark the repository as re-pointed at the git branch ``target``, for seven days at most."""
        await self.cache.set(
            key=self._key(repository_id=repository_id, target=target), value=target, expires=RETARGET_MARKER_TTL_SECONDS
        )

    async def is_retargeted(self, repository_id: str, target: str) -> bool:
        """Whether the repository carries a marker for ``target``. The marker stays in place."""
        return await self.cache.get(key=self._key(repository_id=repository_id, target=target)) is not None

    async def clear(self, repository_id: str, target: str) -> None:
        """Delete the marker for ``target``, and leave the markers for other targets."""
        await self.cache.delete(key=self._key(repository_id=repository_id, target=target))

    @staticmethod
    def _key(repository_id: str, target: str) -> str:
        # A git branch name can hold characters a cache key cannot, so the key carries a digest of it.
        return f"git_retarget:{repository_id}:{hashlib.sha256(target.encode()).hexdigest()}"
