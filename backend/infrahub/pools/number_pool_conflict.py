"""Numbers pools just allocated that another object already holds, and how an operator resolves the conflict."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from infrahub.core.constants import PoolRecordProvenance

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.pools.number_pool_usage import NumberHolder


@dataclass(frozen=True)
class PooledNumber:
    """A number a pool just allocated to one field."""

    field_name: str
    pool_name: str
    value: int
    holding_pool_name: str | None
    """The other pool tracking the number for the holding object, when one does."""


@dataclass(frozen=True)
class PooledNumberConflict:
    """The numbers pools just allocated to the violated fields, which another object already holds."""

    numbers: tuple[PooledNumber, ...]
    node_id: str
    node_label: str | None

    def advice(self) -> str:
        """Return the clause naming the pools, the numbers and the holding object, and how to resolve the conflict."""
        holding_object = (
            f"object '{self.node_label}' ('{self.node_id}')" if self.node_label else f"object '{self.node_id}'"
        )
        if len(self.numbers) > 1:
            return self._numbers_advice(holding_object=holding_object)
        [number] = self.numbers
        allocated = f": the '{number.pool_name}' pool allocated {number.value}, which {holding_object} already holds"
        attach = f"updating object '{self.node_id}' with value {number.value} and from_pool '{number.pool_name}'"
        if number.holding_pool_name is None:
            # A pool reads only its own records, so it offers this number again until the number is attached.
            return f"{allocated}. Attach that number to the pool by {attach}, or change its number, then retry."
        # Attaching alone leaves the other pool offering the same number, so that pool's ranges must stop covering it.
        return (
            f"{allocated} through the '{number.holding_pool_name}' pool, because the ranges of the two pools "
            f"overlap. Attach the numbers in the overlap to one of the pools, for example by {attach}, then change "
            "the ranges of the other pool so they no longer overlap, then retry."
        )

    def _numbers_advice(self, holding_object: str) -> str:
        allocated = " and ".join(
            f"the '{number.pool_name}' pool allocated {number.value} for {number.field_name}"
            + (f" (also tracked by the '{number.holding_pool_name}' pool)" if number.holding_pool_name else "")
            for number in self.numbers
        )
        attach = ", and ".join(
            f"{number.field_name} value {number.value} and from_pool '{number.pool_name}'" for number in self.numbers
        )
        overlap = (
            "; where another pool also tracks a number, the ranges of the two pools overlap, so also change the "
            "ranges of the other pool so they no longer overlap"
            if any(number.holding_pool_name for number in self.numbers)
            else ""
        )
        return (
            f": {allocated}, which {holding_object} already holds. Attach those numbers to their pools by updating "
            f"object '{self.node_id}' with {attach}, or change them{overlap}, then retry."
        )


class NumberPoolNameReader(Protocol):
    """Reads the name of a number pool."""

    async def get_pool_name(self, pool_id: str) -> str | None: ...


class NumberHolderReader(Protocol):
    """Reads an object holding numbers: its label and the pools tracking them."""

    async def read(self, node_id: str, attribute_names: Sequence[str], branch: Branch) -> NumberHolder | None: ...


class NumberPoolConflictFinder:
    """Finds the numbers pools just allocated to the fields of a uniqueness violation, and the object holding them."""

    def __init__(self, pool_name_reader: NumberPoolNameReader, holder_reader: NumberHolderReader) -> None:
        self._pool_name_reader = pool_name_reader
        self._holder_reader = holder_reader

    async def find(
        self, node: Node, fields: Sequence[str], holding_node_ids: Collection[str], branch: Branch
    ) -> PooledNumberConflict | None:
        """Return the numbers pools allocated to `fields` of `node`, or None when no pool allocated one.

        The holding object and the pool names are read only when a pool allocated one of the numbers.
        """
        attribute_names = node.get_schema().attribute_names
        allocated: list[tuple[str, str, int]] = []
        for field in fields:
            if field not in attribute_names:
                continue
            attribute = node.get_attribute(name=field)
            tracking_pool = attribute.tracking_pool
            value = attribute.value
            if (
                tracking_pool is not None
                and tracking_pool.provenance is PoolRecordProvenance.ALLOCATED
                and isinstance(value, int)
            ):
                allocated.append((field, tracking_pool.pool_id, value))
        if not allocated:
            return None
        node_id = min(holding_node_ids)
        holder = await self._holder_reader.read(
            node_id=node_id, attribute_names=[field for field, _, _ in allocated], branch=branch
        )
        holding_pool_ids = holder.tracking_pool_ids if holder is not None else {}
        pool_ids = {pool_id for _, pool_id, _ in allocated} | set(holding_pool_ids.values())
        pool_names = {pool_id: await self._pool_name(pool_id=pool_id) for pool_id in sorted(pool_ids)}
        return PooledNumberConflict(
            numbers=tuple(
                PooledNumber(
                    field_name=field,
                    pool_name=pool_names[pool_id],
                    value=value,
                    holding_pool_name=pool_names[holding_pool_ids[field]]
                    if holding_pool_ids.get(field, pool_id) != pool_id
                    else None,
                )
                for field, pool_id, value in allocated
            ),
            node_id=node_id,
            node_label=holder.label if holder is not None else None,
        )

    async def _pool_name(self, pool_id: str) -> str:
        return await self._pool_name_reader.get_pool_name(pool_id=pool_id) or pool_id
