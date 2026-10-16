from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from infrahub.core.attribute import Integer
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, PoolRecordProvenance
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import NodeNotFoundError, PoolExhaustedError

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.protocols import CoreNumberPool
    from infrahub.pools.attribute_pool_applier import AttributePoolApplier
    from infrahub.pools.number_ranges import PoolRange
    from infrahub.pools.range_refusal import BranchValue
    from infrahub.pools.scope import AllocationScope, Division
    from tests.unit.pools.helpers import InMemoryNumberPool


NODE_ID = "18a0b9e3-0000-0000-0000-00000000aaaa"
ATTRIBUTE_ID = "18a0b9e3-0000-0000-0000-00000000dddd"
POOL_ID = "5c1f6e0a-0000-0000-0000-00000000bbbb"
OTHER_POOL_ID = "5c1f6e0a-0000-0000-0000-00000000eeee"
OTHER_ATTRIBUTE_POOL_ID = "5c1f6e0a-0000-0000-0000-00000000cccc"
ACTOR_ID = "17ce4c8a-6bf1-4b5f-9ec0-5cf6a9d4d1a2"
OTHER_ACTOR_ID = "5b7d2e0c-4f3a-4c1e-9a6b-2d8f1c0e7a41"


@dataclass
class InMemoryNumberPoolFinder:
    pools: list[InMemoryNumberPool]
    tracking_pool_ids: dict[str, str] = field(default_factory=dict)
    tracking_pool_lookups: list[str] = field(default_factory=list)
    """The attribute ids of every tracking pool lookup, in order."""

    async def find(self, pool_ref: str) -> CoreNumberPool:
        for pool in self.pools:
            if pool_ref in {pool.id, pool.name.value}:
                return pool
        raise NodeNotFoundError(node_type=InfrahubKind.NUMBERPOOL, identifier=pool_ref)

    async def get_tracking_pool_id(self, attribute_id: str) -> str | None:
        self.tracking_pool_lookups.append(attribute_id)
        return self.tracking_pool_ids.get(attribute_id)


@dataclass
class InMemoryPoolRangeReader:
    ranges_by_pool_id: dict[str, list[PoolRange]]
    reads: list[str] = field(default_factory=list)
    """The pool ids of every ranges read, in order."""

    async def get_pool_ranges(self, pool_id: str) -> list[PoolRange]:
        self.reads.append(pool_id)
        return list(self.ranges_by_pool_id.get(pool_id, []))


@dataclass
class InMemoryAttributeBranchValues:
    """Holds the number each live branch holds per attribute, and records the attribute ids of every read."""

    values: list[BranchValue] = field(default_factory=list)
    reads: list[list[str]] = field(default_factory=list)

    async def read(self, attribute_ids: list[str]) -> list[BranchValue]:
        self.reads.append(list(attribute_ids))
        return [branch_value for branch_value in self.values if branch_value.attribute_id in attribute_ids]


@dataclass
class PoolCall:
    action: str
    pool_id: str | None
    node_id: str
    attribute_name: str
    user_id: str = ACTOR_ID
    reuse_reservation: bool | None = None
    """Whether an allocation may return the number the pool already holds, None for every other action."""


@dataclass
class RecordingNumberAllocator:
    """Records each allocation, attachment and release in order, and hands out a fixed number unless set to be exhausted."""

    number: int = 42
    exhausted: bool = False
    attach_provenance: PoolRecordProvenance = PoolRecordProvenance.PROVIDED
    """What the pool's record says about the held number once attached, as the write reports it."""
    calls: list[PoolCall] = field(default_factory=list)

    async def allocate(  # noqa: PLR0913, PLR0917
        self,
        pool: CoreNumberPool,
        node: Node,
        attribute: BaseAttribute,
        user_id: str,
        reuse_reservation: bool,
        division: Division | None,
    ) -> int:
        self.calls.append(
            PoolCall(
                action="allocate",
                pool_id=pool.get_id(),
                node_id=node.get_id(),
                attribute_name=attribute.name,
                user_id=user_id,
                reuse_reservation=reuse_reservation,
            )
        )
        if self.exhausted:
            raise PoolExhaustedError(f"Pool tickets ({pool.get_id()}) has no free number left in its ranges.")
        return self.number

    async def attach(
        self, pool: CoreNumberPool, node: Node, attribute: BaseAttribute, user_id: str
    ) -> PoolRecordProvenance:
        self.calls.append(
            PoolCall(
                action="attach",
                pool_id=pool.get_id(),
                node_id=node.get_id(),
                attribute_name=attribute.name,
                user_id=user_id,
            )
        )
        return self.attach_provenance

    async def release(self, attribute: BaseAttribute, user_id: str) -> None:
        self.calls.append(
            PoolCall(
                action="release",
                pool_id=None,
                node_id=attribute.node.get_id(),
                attribute_name=attribute.name,
                user_id=user_id,
            )
        )


class UnscopedDivisionReader:
    """Refuses to read a division, since every pool of these tests allocates from one space."""

    async def read(self, node: Node, scope: AllocationScope, pool_name: str, attribute_name: str) -> Division:
        raise AssertionError(f"no division is read for the unscoped pool {pool_name}")


def make_ticket_attribute(attribute_schema: AttributeSchema, payload: dict[str, Any] | None = None) -> BaseAttribute:
    """Build a ticket attribute as a write would, so `value` and `from_pool` keep whether they were sent."""
    branch = Branch(name="main")
    at = Timestamp()
    node = Node(
        schema=NodeSchema(name="Ticket", namespace="Testing", attributes=[attribute_schema]), branch=branch, at=at
    )
    node.id = NODE_ID
    return Integer(name=attribute_schema.name, schema=attribute_schema, branch=branch, at=at, node=node, data=payload)


def make_ticket_id(payload: dict[str, Any] | None = None, saved: bool = False) -> BaseAttribute:
    attribute = make_ticket_attribute(AttributeSchema(name="ticket_id", kind="Number", optional=True), payload=payload)
    if saved:
        attribute.id = ATTRIBUTE_ID
    return attribute


async def apply_on_create(applier: AttributePoolApplier, attribute: BaseAttribute, allocate: bool = True) -> None:
    await applier.apply(node=attribute.node, attribute=attribute, allocate=allocate, user_id=ACTOR_ID)


def untracked_attach_message(ranges: str, value: int = 900) -> str:
    return (
        f"The tickets pool cannot track {value} on 'ticket_id', because {value} is outside its ranges: {ranges}. "
        f"Send a number inside those ranges. at ticket_id.from_pool"
    )
