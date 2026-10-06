from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from infrahub.core.attribute import Integer
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import NodeNotFoundError, PoolExhaustedError, ValidationError
from infrahub.pools.attribute_pool_applier import AttributePoolApplier

from .helpers import InMemoryNumberPool

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.protocols import CoreNumberPool

NODE_ID = "18a0b9e3-0000-0000-0000-00000000aaaa"


@dataclass
class InMemoryNumberPoolFinder:
    pools: list[InMemoryNumberPool]

    async def find(self, pool_ref: str) -> CoreNumberPool:
        for pool in self.pools:
            if pool_ref in {pool.id, pool.name.value}:
                return pool
        raise NodeNotFoundError(node_type=InfrahubKind.NUMBERPOOL, identifier=pool_ref)


@dataclass
class AllocationCall:
    pool_id: str
    node_id: str
    attribute_name: str


@dataclass
class RecordingNumberAllocator:
    """Records each allocation in order and hands out a fixed number, or raises when set to be exhausted."""

    number: int = 42
    exhausted: bool = False
    calls: list[AllocationCall] = field(default_factory=list)

    async def allocate(self, pool: CoreNumberPool, node: Node, attribute: BaseAttribute) -> int:
        self.calls.append(AllocationCall(pool_id=pool.get_id(), node_id=node.get_id(), attribute_name=attribute.name))
        if self.exhausted:
            raise PoolExhaustedError("There are no more values available in this pool.")
        return self.number


POOL_ID = "5c1f6e0a-0000-0000-0000-00000000bbbb"
OTHER_ATTRIBUTE_POOL_ID = "5c1f6e0a-0000-0000-0000-00000000cccc"


def _ticket_attribute(attribute_schema: AttributeSchema) -> BaseAttribute:
    branch = Branch(name="main")
    at = Timestamp()
    node = Node(
        schema=NodeSchema(name="Ticket", namespace="Testing", attributes=[attribute_schema]), branch=branch, at=at
    )
    node.id = NODE_ID
    return Integer(name=attribute_schema.name, schema=attribute_schema, branch=branch, at=at, node=node, data=None)


@pytest.fixture
def allocator() -> RecordingNumberAllocator:
    return RecordingNumberAllocator()


@pytest.fixture
def applier(allocator: RecordingNumberAllocator) -> AttributePoolApplier:
    return AttributePoolApplier(
        pool_finder=InMemoryNumberPoolFinder(
            pools=[
                InMemoryNumberPool(id=POOL_ID, name="tickets"),
                InMemoryNumberPool(id=OTHER_ATTRIBUTE_POOL_ID, name="titles", node_attribute="title"),
            ]
        ),
        number_allocator=allocator,
    )


@pytest.fixture
def ticket_id() -> BaseAttribute:
    return _ticket_attribute(AttributeSchema(name="ticket_id", kind="Number", optional=True))


async def test_pool_named_by_id_gives_the_attribute_its_number(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator, ticket_id: BaseAttribute
) -> None:
    ticket_id.from_pool = {"id": POOL_ID}

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True)

    assert ticket_id.value == 42
    assert ticket_id.from_pool == {"id": POOL_ID}
    assert allocator.calls == [AllocationCall(pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id")]


async def test_pool_named_by_name_is_recorded_by_its_id(
    applier: AttributePoolApplier, ticket_id: BaseAttribute
) -> None:
    ticket_id.from_pool = {"id": "tickets"}

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True)

    assert ticket_id.from_pool == {"id": POOL_ID}
    assert ticket_id.value == 42


async def test_without_allocation_only_the_pool_is_resolved(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator, ticket_id: BaseAttribute
) -> None:
    ticket_id.from_pool = {"id": "tickets"}

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=False)

    assert ticket_id.from_pool == {"id": POOL_ID}
    assert ticket_id.value is None
    assert allocator.calls == []


async def test_an_attribute_naming_no_pool_is_left_alone(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator, ticket_id: BaseAttribute
) -> None:
    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True)

    assert ticket_id.from_pool is None
    assert ticket_id.value is None
    assert allocator.calls == []


async def test_a_number_pool_attribute_draws_from_the_pool_its_schema_declares(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    attribute = _ticket_attribute(
        AttributeSchema(
            name="ticket_id", kind="NumberPool", parameters=NumberPoolParameters(number_pool_id=POOL_ID), optional=True
        )
    )

    await applier.apply(node=attribute.node, attribute=attribute, allocate=True)

    assert attribute.from_pool == {"id": POOL_ID}
    assert attribute.is_default is False
    assert attribute.value == 42
    assert allocator.calls == [AllocationCall(pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id")]


async def test_a_number_pool_attribute_without_a_provisioned_pool_is_refused(applier: AttributePoolApplier) -> None:
    attribute = _ticket_attribute(
        AttributeSchema(name="ticket_id", kind="NumberPool", parameters=NumberPoolParameters(), optional=True)
    )

    with pytest.raises(ValidationError, match=r"^The pool for ticket_id has not been provisioned yet\. at ticket_id$"):
        await applier.apply(node=attribute.node, attribute=attribute, allocate=True)


async def test_from_pool_without_an_id_is_refused(applier: AttributePoolApplier, ticket_id: BaseAttribute) -> None:
    ticket_id.from_pool = {"identifier": "no-id"}

    with pytest.raises(ValidationError, match=r"^No pool ID specified in from_pool\. at ticket_id\.from_pool$"):
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True)


async def test_an_unknown_pool_is_refused(applier: AttributePoolApplier, ticket_id: BaseAttribute) -> None:
    ticket_id.from_pool = {"id": "no-such-pool"}

    with pytest.raises(
        ValidationError,
        match=r"^The pool requested \{'id': 'no-such-pool'\} was not found\. at ticket_id\.from_pool$",
    ):
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True)


async def test_a_pool_for_another_attribute_is_refused(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator, ticket_id: BaseAttribute
) -> None:
    ticket_id.from_pool = {"id": OTHER_ATTRIBUTE_POOL_ID}

    with pytest.raises(
        ValidationError, match=r"^The titles pool can't be used for 'ticket_id'\. at ticket_id\.from_pool$"
    ):
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True)
    assert allocator.calls == []


async def test_an_exhausted_pool_is_reported_against_the_attribute(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator, ticket_id: BaseAttribute
) -> None:
    ticket_id.from_pool = {"id": POOL_ID}
    allocator.exhausted = True

    with pytest.raises(ValidationError, match=r"^The pool TestingTicket is exhausted\. at ticket_id\.from_pool$"):
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True)
    assert ticket_id.value is None
