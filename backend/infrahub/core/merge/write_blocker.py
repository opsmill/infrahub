from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.utils import InfrahubStringEnum

if TYPE_CHECKING:
    from infrahub.services.adapters.cache import InfrahubCache

MERGE_PROTECTED_CACHE_KEY = "merge:protected"

_SEPARATOR = "::"


class MergeProtectionState(InfrahubStringEnum):
    """State carried by the merge protection cache key.

    These mirror the durable branch statuses that block writes, but they live in the cache layer so
    the write gate can read them with a single lookup without coupling to the full branch-status enum.
    """

    MERGING = "MERGING"
    MERGE_FAILED = "MERGE_FAILED"


@dataclass(frozen=True)
class MergeProtection:
    branch: str
    state: MergeProtectionState


class MergeWriteBlocker:
    """Set, get, and delete the key and value for blocking writes during a merge operation."""

    def __init__(self, cache: InfrahubCache) -> None:
        self.cache = cache

    def _serialize(self, *, branch: str, state: MergeProtectionState) -> str:
        return f"{branch}{_SEPARATOR}{state.value}"

    def _parse(self, value: str | None) -> MergeProtection | None:
        """Parse a cache value of the form ``"{branch}::{state}"``.

        Returns ``None`` for a missing or malformed value. Branch names cannot contain ``:`` so the
        final separator unambiguously splits the branch name from the state.
        """
        if not value:
            return None
        branch, separator, raw_state = value.rpartition(_SEPARATOR)
        if not separator or not branch:
            return None
        try:
            state = MergeProtectionState(raw_state)
        except ValueError:
            return None
        return MergeProtection(branch=branch, state=state)

    async def set(self, *, branch: str, state: MergeProtectionState) -> None:
        await self.cache.set(key=MERGE_PROTECTED_CACHE_KEY, value=self._serialize(branch=branch, state=state))

    async def get(self) -> MergeProtection | None:
        return self._parse(await self.cache.get(key=MERGE_PROTECTED_CACHE_KEY))

    async def delete(self) -> None:
        await self.cache.delete(key=MERGE_PROTECTED_CACHE_KEY)
