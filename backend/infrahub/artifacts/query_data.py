from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from infrahub.services.adapters.cache import InfrahubCache

# An expired fingerprint costs one extra rendering, so entries expire rather than being removed with their branch.
QUERY_DATA_FINGERPRINT_TTL_SECONDS = 30 * 24 * 60 * 60


def fingerprint_query_data(data: dict[str, Any]) -> str:
    """Return a hash of a query response that does not depend on the order of its keys."""
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


class RenderedQueryData:
    """Fingerprints of the query response each artifact on a branch was last rendered from.

    A missing fingerprint means the artifact's rendering cannot be compared with the current data.
    """

    def __init__(self, cache: InfrahubCache) -> None:
        self.cache = cache

    @staticmethod
    def _key(branch_id: str, artifact_id: str) -> str:
        return f"artifact:query_data:{branch_id}:{artifact_id}"

    async def save(self, branch_id: str, artifact_id: str, fingerprint: str) -> None:
        await self.cache.set(
            key=self._key(branch_id=branch_id, artifact_id=artifact_id),
            value=fingerprint,
            expires=QUERY_DATA_FINGERPRINT_TTL_SECONDS,
        )

    async def forget(self, branch_id: str, artifact_id: str) -> None:
        await self.cache.delete(key=self._key(branch_id=branch_id, artifact_id=artifact_id))

    async def get_many(self, branch_id: str, artifact_ids: list[str]) -> dict[str, str | None]:
        values = await self.cache.get_values(
            keys=[self._key(branch_id=branch_id, artifact_id=artifact_id) for artifact_id in artifact_ids]
        )
        return dict(zip(artifact_ids, values, strict=True))
