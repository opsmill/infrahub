from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from infrahub.core.attribute import ListAttributeOptional, String
from infrahub.core.branch import Branch
from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.pools.number_pool_range_reconciler import ReconcilableRangeStore

if TYPE_CHECKING:
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool as CoreNumberPoolNode
    from infrahub.pools.number_ranges import EffectiveSpace, PoolRange

TICKET_KIND = "TestingTicket"


class InMemoryNumberPool(CoreNumberPool):
    """A number pool held in memory, carrying only the attributes that decide who may draw from it."""

    def __init__(self, id: str, name: str, node: str = TICKET_KIND, node_attribute: str = "ticket_id") -> None:
        self.id = id
        branch = Branch(name="main")
        at = Timestamp()
        attribute_schemas = [
            AttributeSchema(name=attr_name, kind="Text") for attr_name in ("name", "node", "node_attribute")
        ]
        owner = Node(
            schema=NodeSchema(name="NumberPool", namespace="Core", attributes=attribute_schemas), branch=branch, at=at
        )
        owner.id = id
        name_schema, node_schema, node_attribute_schema = attribute_schemas
        self.name = String(name="name", schema=name_schema, branch=branch, at=at, node=owner, data=name)
        self.node = String(name="node", schema=node_schema, branch=branch, at=at, node=owner, data=node)
        self.node_attribute = String(
            name="node_attribute", schema=node_attribute_schema, branch=branch, at=at, node=owner, data=node_attribute
        )
        scope_schema = AttributeSchema(name="allocation_scope", kind="List", optional=True)
        self.allocation_scope = ListAttributeOptional(
            name="allocation_scope", schema=scope_schema, branch=branch, at=at, node=owner, data=None
        )

    def get_id(self) -> str:
        return self.id


class InMemoryNumberPoolNumbers:
    """Holds a pool's ranges, the numbers it accounts for and the values its target holds; records free lookups."""

    def __init__(
        self, ranges: list[PoolRange] | None = None, accounted: set[int] | None = None, taken: set[int] | None = None
    ) -> None:
        self.ranges = ranges or []
        self.accounted = accounted or set()
        self.taken = taken or set()
        self.free_lookups: list[tuple[int, int]] = []

    async def get_pool_ranges(self, pool_id: str, at: Timestamp | None = None) -> list[PoolRange]:
        return list(self.ranges)

    async def get_taken(self, pool: CoreNumberPoolNode, branch: Branch, space: EffectiveSpace) -> set[int]:
        return {value for value in self.taken if space.contains(value)}

    async def get_free(self, pool: CoreNumberPoolNode, branch: Branch, min_value: int, max_value: int) -> int | None:
        self.free_lookups.append((min_value, max_value))
        return next((value for value in range(min_value, max_value + 1) if value not in self.accounted), None)


@dataclass(frozen=True)
class PoolReference:
    id: str

    def get_id(self) -> str:
        return self.id


@dataclass
class StoredInteger:
    value: int


@dataclass
class StoredOptionalInteger:
    value: int | None


@dataclass
class InMemoryRange:
    id: str
    start: StoredInteger
    end: StoredInteger
    allocation_weight: StoredOptionalInteger

    def get_id(self) -> str:
        return self.id

    @property
    def details(self) -> tuple[str, int, int, int | None]:
        return self.id, self.start.value, self.end.value, self.allocation_weight.value


class InMemoryRangeStore(ReconcilableRangeStore[InMemoryRange, PoolReference]):
    """Holds the ranges of one pool, named stored-<n> and created-<n>, and records every write in order."""

    def __init__(self, ranges: list[tuple[int, int, int | None]] | None = None) -> None:
        self.ranges = {
            f"stored-{index}": InMemoryRange(
                id=f"stored-{index}",
                start=StoredInteger(value=start),
                end=StoredInteger(value=end),
                allocation_weight=StoredOptionalInteger(value=weight),
            )
            for index, (start, end, weight) in enumerate(ranges or [])
        }
        self.writes: list[tuple[str, str]] = []

    @override
    async def get_ranges(self, pool_id: str) -> list[InMemoryRange]:
        return sorted(self.ranges.values(), key=lambda pool_range: pool_range.start.value)

    @override
    async def create_range(
        self,
        pool: PoolReference,
        start: int,
        end: int,
        weight: int | None = None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> InMemoryRange:
        pool_range = InMemoryRange(
            id=f"created-{len(self.writes)}",
            start=StoredInteger(value=start),
            end=StoredInteger(value=end),
            allocation_weight=StoredOptionalInteger(value=weight),
        )
        self.ranges[pool_range.id] = pool_range
        self.writes.append(("create", pool_range.id))
        return pool_range

    @override
    async def save_range(
        self,
        pool_range: InMemoryRange,
        start: int,
        end: int,
        weight: int | None,
        at: Timestamp | None = None,
        user_id: str = SYSTEM_USER_ID,
    ) -> None:
        pool_range.start.value = start
        pool_range.end.value = end
        pool_range.allocation_weight.value = weight
        self.writes.append(("save", pool_range.id))

    @override
    async def delete_range(
        self, pool_range: InMemoryRange, at: Timestamp | None = None, user_id: str = SYSTEM_USER_ID
    ) -> None:
        del self.ranges[pool_range.id]
        self.writes.append(("delete", pool_range.id))
