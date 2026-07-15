from __future__ import annotations

import json
from typing import TYPE_CHECKING

from infrahub_sdk.diff import NodeDiff
from pydantic import TypeAdapter

from infrahub.exceptions import ResourceNotFoundError
from infrahub.message_bus.types import KVTTL

if TYPE_CHECKING:
    from infrahub.services.adapters.cache import InfrahubCache

_NODE_DIFFS_ADAPTER = TypeAdapter(list[NodeDiff])


class MergeDiffSummaryCache:
    """Store and load a per-merge diff summary, keyed by the (freeze-stable) diff-root uuid."""

    def __init__(self, cache: InfrahubCache) -> None:
        self._cache = cache

    async def set(self, diff_id: str, diff_summary: list[NodeDiff]) -> None:
        await self._cache.set(key=self._key(diff_id), value=json.dumps(diff_summary), expires=KVTTL.TWO_HOURS)

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
            return _NODE_DIFFS_ADAPTER.validate_json(summary_payload)
        except ResourceNotFoundError:
            raise
        except Exception as exc:
            raise ResourceNotFoundError(
                message=f"Merge diff summary for diff {diff_id} could not be loaded from the cache"
            ) from exc

    @staticmethod
    def _key(diff_id: str) -> str:
        return f"branch_merge:diff_id:{diff_id}:diff_summary"
