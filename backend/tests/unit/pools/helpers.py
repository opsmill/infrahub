from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.attribute import String
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.timestamp import Timestamp

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
