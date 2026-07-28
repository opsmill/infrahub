from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.exceptions import ResourceNotFoundError
from infrahub.message_bus.types import KVTTL

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.diff.summary_serializer import DiffSummarySerializer
    from infrahub.services.adapters.cache import InfrahubCache


class DiffSummaryCache:
    """Store and load a diff summary, keyed by a caller-supplied namespace and the diff id."""

    def __init__(self, cache: InfrahubCache, serializer: DiffSummarySerializer, key_namespace: str) -> None:
        self._cache = cache
        self._serializer = serializer
        self._key_namespace = key_namespace

    async def set(self, diff_id: str, diff_summary: list[NodeDiff]) -> None:
        await self.set_payload(diff_id=diff_id, payload=self._serializer.dump(diff_summary))

    async def set_payload(self, diff_id: str, payload: str) -> None:
        """Store an already-serialized summary, avoiding a second dump when the caller measured it."""
        await self._cache.set(key=self._key(diff_id), value=payload, expires=KVTTL.TWO_HOURS)

    async def get(self, diff_id: str) -> list[NodeDiff]:
        """Load a diff summary.

        Every load failure -- a missing entry, an unreachable cache, or a payload that does not
        parse into a list of node diffs -- normalizes to a single exception so the caller has one
        fallback branch and no load failure can escape to the caller.

        Raises:
            ResourceNotFoundError: the summary is missing or cannot be loaded.

        """
        try:
            summary_payload = await self._cache.get(key=self._key(diff_id))
            if not summary_payload:
                raise ResourceNotFoundError(message=f"Diff summary for {diff_id} was not found in the cache")
            return self._serializer.load(summary_payload)
        except ResourceNotFoundError:
            raise
        except Exception as exc:
            raise ResourceNotFoundError(
                message=f"Diff summary for {diff_id} could not be loaded from the cache"
            ) from exc

    def _key(self, diff_id: str) -> str:
        return f"{self._key_namespace}:diff_id:{diff_id}:diff_summary"
