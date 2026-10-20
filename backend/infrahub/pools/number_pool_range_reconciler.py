from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.schema.attribute_parameters import NumberPoolRangeParameters

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.timestamp import Timestamp


class _IntegerValue(Protocol):
    @property
    def value(self) -> int: ...


class _OptionalIntegerValue(Protocol):
    @property
    def value(self) -> int | None: ...


class Identified(Protocol):
    def get_id(self) -> str: ...


class StoredRange(Identified, Protocol):
    """A range as the reconciler reads it from its store."""

    @property
    def start(self) -> _IntegerValue: ...

    @property
    def end(self) -> _IntegerValue: ...

    @property
    def allocation_weight(self) -> _OptionalIntegerValue: ...


class ReconcilableRangeStore[RangeT: StoredRange, PoolT: Identified](Protocol):
    """Reads and writes the ranges of a pool for the reconciler."""

    async def get_ranges(self, pool_id: str) -> Sequence[RangeT]: ...

    async def create_range(
        self,
        pool: PoolT,
        start: int,
        end: int,
        weight: int | None = None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> RangeT: ...

    async def save_range(
        self,
        pool_range: RangeT,
        start: int,
        end: int,
        weight: int | None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> None: ...

    async def delete_range(
        self, pool_range: RangeT, at: Timestamp | None = None, user_id: str = SYSTEM_USER_ID
    ) -> None: ...


@dataclass(frozen=True)
class RangeReconciliation[RangeT: StoredRange]:
    """The pool's ranges once reconciled, lowest start first, and the ranges the reconciliation wrote."""

    ranges: list[RangeT]
    created: list[RangeT]
    updated: list[RangeT]
    deleted: list[RangeT]

    @property
    def changed(self) -> bool:
        return bool(self.created or self.updated or self.deleted)


@dataclass(frozen=True)
class _RangeChanges:
    to_create: list[NumberPoolRangeParameters] = field(default_factory=list)
    to_reweight: list[tuple[str, NumberPoolRangeParameters]] = field(default_factory=list)
    to_delete: list[str] = field(default_factory=list)


class NumberPoolRangeReconciler[RangeT: StoredRange, PoolT: Identified]:
    """Rewrites the ranges of a pool so they match a declared set."""

    def __init__(self, range_store: ReconcilableRangeStore[RangeT, PoolT]) -> None:
        self.range_store = range_store

    async def reconcile(
        self,
        pool: PoolT,
        declared: Sequence[NumberPoolRangeParameters],
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> RangeReconciliation[RangeT]:
        """Make the pool hold exactly the declared ranges, leaving the numbers it has handed out untouched.

        A stored range declared again with the same bounds is kept, with its weight rewritten when it differs. Every
        other declared range is created and every other stored range is deleted, so a range never changes bounds.
        """
        pool_id = pool.get_id()
        stored_ranges = list(await self.range_store.get_ranges(pool_id=pool_id))
        stored_by_id = {item.get_id(): item for item in stored_ranges}
        changes = self._plan_changes(declared=declared, stored_by_id=stored_by_id)

        deleted: list[RangeT] = []
        for range_id in changes.to_delete:
            await self.range_store.delete_range(pool_range=stored_by_id[range_id], at=at, user_id=user_id)
            deleted.append(stored_by_id[range_id])
        updated: list[RangeT] = []
        for range_id, declared_range in changes.to_reweight:
            await self._save(stored=stored_by_id[range_id], declared=declared_range, at=at, user_id=user_id)
            updated.append(stored_by_id[range_id])
        created = [
            await self.range_store.create_range(
                pool=pool,
                start=declared_range.start,
                end=declared_range.end,
                weight=declared_range.weight,
                at=at,
                user_id=user_id,
            )
            for declared_range in changes.to_create
        ]

        return await self._result(
            pool_id=pool_id, stored_ranges=stored_ranges, created=created, updated=updated, deleted=deleted
        )

    async def rewrite_single_range(
        self,
        pool: PoolT,
        declared: NumberPoolRangeParameters,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> RangeReconciliation[RangeT]:
        """Make the pool hold only the declared range, rewriting the range it holds in place so it keeps its identity.

        Raises:
            ValueError: When the pool holds more than one range.

        """
        pool_id = pool.get_id()
        stored_ranges = list(await self.range_store.get_ranges(pool_id=pool_id))
        if len(stored_ranges) > 1:
            raise ValueError(f"Number pool {pool_id} holds {len(stored_ranges)} ranges, a single range is rewritten")

        created: list[RangeT] = []
        updated: list[RangeT] = []
        if not stored_ranges:
            created.append(
                await self.range_store.create_range(
                    pool=pool,
                    start=declared.start,
                    end=declared.end,
                    weight=declared.weight,
                    at=at,
                    user_id=user_id,
                )
            )
        else:
            (stored,) = stored_ranges
            if self._parameters(stored=stored) != declared:
                await self._save(stored=stored, declared=declared, at=at, user_id=user_id)
                updated.append(stored)

        return await self._result(
            pool_id=pool_id, stored_ranges=stored_ranges, created=created, updated=updated, deleted=[]
        )

    def _plan_changes(
        self, declared: Sequence[NumberPoolRangeParameters], stored_by_id: dict[str, RangeT]
    ) -> _RangeChanges:
        stored = {range_id: self._parameters(stored=item) for range_id, item in stored_by_id.items()}
        stored_by_bounds = {(item.start, item.end): range_id for range_id, item in stored.items()}
        changes = _RangeChanges()
        for declared_range in sorted(declared, key=lambda item: (item.start, item.end)):
            range_id = stored_by_bounds.pop((declared_range.start, declared_range.end), None)
            if range_id is None:
                changes.to_create.append(declared_range)
            elif stored[range_id].weight != declared_range.weight:
                changes.to_reweight.append((range_id, declared_range))
        changes.to_delete.extend(sorted(stored_by_bounds.values(), key=lambda range_id: stored[range_id].start))
        return changes

    def _parameters(self, stored: RangeT) -> NumberPoolRangeParameters:
        return NumberPoolRangeParameters(
            start=stored.start.value, end=stored.end.value, weight=stored.allocation_weight.value
        )

    async def _result(
        self,
        pool_id: str,
        stored_ranges: list[RangeT],
        created: list[RangeT],
        updated: list[RangeT],
        deleted: list[RangeT],
    ) -> RangeReconciliation[RangeT]:
        if created or updated or deleted:
            stored_ranges = list(await self.range_store.get_ranges(pool_id=pool_id))
        return RangeReconciliation(ranges=stored_ranges, created=created, updated=updated, deleted=deleted)

    async def _save(
        self, stored: RangeT, declared: NumberPoolRangeParameters, at: Timestamp | None, user_id: str
    ) -> None:
        await self.range_store.save_range(
            pool_range=stored, start=declared.start, end=declared.end, weight=declared.weight, at=at, user_id=user_id
        )
