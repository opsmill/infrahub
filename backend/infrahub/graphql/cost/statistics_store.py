from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from infrahub.graphql.cost.constants import STATISTICS_KIND_KEY_TEMPLATE, STATISTICS_POINTER_KEY
from infrahub.graphql.cost.models import KindStatistics, StatisticsPointer, StatisticsSnapshot

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from infrahub.services.adapters.cache import InfrahubCache


def _kind_key(version: int, kind: str) -> str:
    return STATISTICS_KIND_KEY_TEMPLATE.format(version=version, kind=kind)


class StatisticsStore:
    """Versions of the statistics in the cache: one key for each kind, and a pointer to the version to read."""

    def __init__(self, cache: InfrahubCache) -> None:
        self.cache = cache

    async def read_pointer(self) -> StatisticsPointer | None:
        value = await self.cache.get(key=STATISTICS_POINTER_KEY)
        return StatisticsPointer.from_json(value) if value is not None else None

    async def read_kinds(self, version: int, kinds: Sequence[str]) -> dict[str, KindStatistics]:
        """Return the statistics of the kinds that still have a key in the version, by kind."""
        if not kinds:
            return {}
        values = await self.cache.get_values(keys=[_kind_key(version=version, kind=kind) for kind in kinds])
        return {
            kind: KindStatistics.from_json(value)
            for kind, value in zip(kinds, values, strict=True)
            if value is not None
        }

    async def publish(
        self, kinds: Sequence[KindStatistics], branch: str, computed_at: datetime, schema_hash: str
    ) -> StatisticsPointer:
        """Write the statistics as the version after the current one, then point readers at it.

        Every kind key is written before the pointer, so a reader never sees part of a version. Keys that an
        interrupted run left under the new version are deleted first, and the keys of the previous version once
        the pointer has moved.
        """
        previous = await self.read_pointer()
        version = previous.version + 1 if previous is not None else 1
        await self._delete_version(version=version)

        for statistics in kinds:
            await self.cache.set(key=_kind_key(version=version, kind=statistics.kind), value=statistics.to_json())
        pointer = StatisticsPointer(
            version=version,
            branch=branch,
            computed_at=computed_at,
            schema_hash=schema_hash,
            kinds=tuple(statistics.kind for statistics in kinds),
        )
        await self.cache.set(key=STATISTICS_POINTER_KEY, value=pointer.to_json())

        if previous is not None:
            await self._delete_version(version=previous.version)
        return pointer

    async def _delete_version(self, version: int) -> None:
        for key in await self.cache.list_keys(filter_pattern=_kind_key(version=version, kind="*")):
            await self.cache.delete(key=key)


class StatisticsSnapshotHolder:
    """The statistics version a process loaded last, reloaded only when the pointer names another version."""

    def __init__(self) -> None:
        self._snapshot: StatisticsSnapshot | None = None
        self._load_lock = asyncio.Lock()

    async def get(self, store: StatisticsStore) -> StatisticsSnapshot | None:
        """Return the statistics of the version the pointer names, or None when no version exists.

        A kind whose key is missing makes the holder read the pointer once more, because a refresh deletes the
        keys of a version once it has moved the pointer; a kind still missing after that has no statistics.
        """
        pointer = await store.read_pointer()
        if pointer is None:
            return None
        snapshot = self._snapshot
        if snapshot is not None and snapshot.pointer.version == pointer.version:
            return snapshot

        async with self._load_lock:
            snapshot = self._snapshot
            if snapshot is None or snapshot.pointer.version != pointer.version:
                snapshot = await self._load(store=store, pointer=pointer)
                self._snapshot = snapshot
            return snapshot

    async def _load(self, store: StatisticsStore, pointer: StatisticsPointer) -> StatisticsSnapshot:
        kinds = await store.read_kinds(version=pointer.version, kinds=pointer.kinds)
        if len(kinds) == len(pointer.kinds):
            return StatisticsSnapshot(pointer=pointer, kinds=kinds)

        latest = await store.read_pointer()
        if latest is None or latest.version == pointer.version:
            return StatisticsSnapshot(pointer=pointer, kinds=kinds)
        return StatisticsSnapshot(
            pointer=latest, kinds=await store.read_kinds(version=latest.version, kinds=latest.kinds)
        )
