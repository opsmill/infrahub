from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.exceptions import ResourceNotFoundError
from infrahub.message_bus.types import KVTTL

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.diff.summary_serializer import DiffSummarySerializer
    from infrahub.services.adapters.cache import InfrahubCache


class MergeDiffSummaryCache:
    """Store and load a per-merge diff summary, keyed by the (freeze-stable) diff-root uuid."""

    def __init__(self, cache: InfrahubCache, serializer: DiffSummarySerializer) -> None:
        self._cache = cache
        self._serializer = serializer

    async def set(self, diff_id: str, diff_summary: list[NodeDiff]) -> None:
        await self._cache.set(
            key=self._key(diff_id), value=self._serializer.dump(diff_summary), expires=KVTTL.TWO_HOURS
        )

    async def get(self, diff_id: str) -> list[NodeDiff]:
        """Load a merge diff summary.

        Every load failure -- a missing entry, an unreachable cache, or a payload that does not
        parse into a list of node diffs -- normalizes to a single exception so the caller has one
        fallback branch and no load failure can escape to the merge follow-up.

        Raises:
            ResourceNotFoundError: the summary is missing or cannot be loaded.

        """
        try:
            summary_payload = await self._cache.get(key=self._key(diff_id))
            if not summary_payload:
                raise ResourceNotFoundError(message=f"Merge diff summary for diff {diff_id} was not found in the cache")
            return self._serializer.load(summary_payload)
        except ResourceNotFoundError:
            raise
        except Exception as exc:
            raise ResourceNotFoundError(
                message=f"Merge diff summary for diff {diff_id} could not be loaded from the cache"
            ) from exc

    @staticmethod
    def _key(diff_id: str) -> str:
        return f"branch_merge:diff_id:{diff_id}:diff_summary"
