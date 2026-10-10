from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.attribute import Integer
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, PoolRecordProvenance
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import NodeNotFoundError, PoolExhaustedError, ValidationError
from infrahub.pools.attribute_pool_applier import AttributePoolApplier
from infrahub.pools.intent import FromPoolIntentResolver

from .helpers import InMemoryNumberPool

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.protocols import CoreNumberPool
    from infrahub.pools.scope import AllocationScope, Division

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

    async def find(self, pool_ref: str) -> CoreNumberPool:
        for pool in self.pools:
            if pool_ref in {pool.id, pool.name.value}:
                return pool
        raise NodeNotFoundError(node_type=InfrahubKind.NUMBERPOOL, identifier=pool_ref)

    async def get_tracking_pool_id(self, attribute_id: str) -> str | None:
        return self.tracking_pool_ids.get(attribute_id)


@dataclass
class PoolCall:
    action: str
    pool_id: str | None
    node_id: str
    attribute_name: str
    user_id: str = ACTOR_ID


@dataclass
class RecordingNumberAllocator:
    """Records each allocation, attachment and release in order, and hands out a fixed number unless set to be exhausted."""

    number: int = 42
    exhausted: bool = False
    calls: list[PoolCall] = field(default_factory=list)

    async def allocate(
        self, pool: CoreNumberPool, node: Node, attribute: BaseAttribute, user_id: str, division: Division | None
    ) -> int:
        self.calls.append(
            PoolCall(
                action="allocate",
                pool_id=pool.get_id(),
                node_id=node.get_id(),
                attribute_name=attribute.name,
                user_id=user_id,
            )
        )
        if self.exhausted:
            raise PoolExhaustedError(f"Pool tickets ({pool.get_id()}) has no free number left in its ranges.")
        return self.number

    async def attach(self, pool: CoreNumberPool, node: Node, attribute: BaseAttribute, user_id: str) -> None:
        self.calls.append(
            PoolCall(
                action="attach",
                pool_id=pool.get_id(),
                node_id=node.get_id(),
                attribute_name=attribute.name,
                user_id=user_id,
            )
        )

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


def _ticket_attribute(attribute_schema: AttributeSchema, payload: dict[str, Any] | None = None) -> BaseAttribute:
    """Build a ticket attribute as a write would, so `value` and `from_pool` keep whether they were sent."""
    branch = Branch(name="main")
    at = Timestamp()
    node = Node(
        schema=NodeSchema(name="Ticket", namespace="Testing", attributes=[attribute_schema]), branch=branch, at=at
    )
    node.id = NODE_ID
    return Integer(name=attribute_schema.name, schema=attribute_schema, branch=branch, at=at, node=node, data=payload)


def _ticket_id(payload: dict[str, Any] | None = None, saved: bool = False) -> BaseAttribute:
    attribute = _ticket_attribute(AttributeSchema(name="ticket_id", kind="Number", optional=True), payload=payload)
    if saved:
        attribute.id = ATTRIBUTE_ID
    return attribute


@pytest.fixture
def finder() -> InMemoryNumberPoolFinder:
    return InMemoryNumberPoolFinder(
        pools=[
            InMemoryNumberPool(id=POOL_ID, name="tickets"),
            InMemoryNumberPool(id=OTHER_POOL_ID, name="other-tickets"),
            InMemoryNumberPool(id=OTHER_ATTRIBUTE_POOL_ID, name="titles", node_attribute="title"),
        ]
    )


@pytest.fixture
def allocator() -> RecordingNumberAllocator:
    return RecordingNumberAllocator()


@pytest.fixture
def applier(finder: InMemoryNumberPoolFinder, allocator: RecordingNumberAllocator) -> AttributePoolApplier:
    return AttributePoolApplier(
        pool_finder=finder,
        number_allocator=allocator,
        intent_resolver=FromPoolIntentResolver(),
        division_reader=UnscopedDivisionReader(),
    )


async def _apply_on_create(applier: AttributePoolApplier, attribute: BaseAttribute, allocate: bool = True) -> None:
    await applier.apply(node=attribute.node, attribute=attribute, allocate=allocate, user_id=ACTOR_ID)


async def test_pool_named_by_id_gives_the_attribute_its_number(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = _ticket_id(payload={"from_pool": {"id": POOL_ID}})

    await _apply_on_create(applier=applier, attribute=ticket_id)

    assert ticket_id.value == 42
    assert ticket_id.from_pool == {"id": POOL_ID}
    assert ticket_id.pool_provenance is PoolRecordProvenance.ALLOCATED
    assert allocator.calls == [
        PoolCall(action="allocate", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id")
    ]


async def test_the_account_making_the_write_reaches_the_allocator(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = _ticket_id(payload={"from_pool": {"id": POOL_ID}})

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=OTHER_ACTOR_ID)

    assert allocator.calls == [
        PoolCall(
            action="allocate", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id", user_id=OTHER_ACTOR_ID
        )
    ]


async def test_pool_named_by_name_is_recorded_by_its_id(applier: AttributePoolApplier) -> None:
    ticket_id = _ticket_id(payload={"from_pool": {"id": "tickets"}})

    await _apply_on_create(applier=applier, attribute=ticket_id)

    assert ticket_id.from_pool == {"id": POOL_ID}
    assert ticket_id.value == 42


async def test_without_allocation_only_the_pool_is_resolved(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = _ticket_id(payload={"from_pool": {"id": "tickets"}})

    await _apply_on_create(applier=applier, attribute=ticket_id, allocate=False)

    assert ticket_id.from_pool == {"id": POOL_ID}
    assert ticket_id.value is None
    assert allocator.calls == []


async def test_an_attribute_naming_no_pool_is_left_alone(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = _ticket_id()

    await _apply_on_create(applier=applier, attribute=ticket_id)

    assert ticket_id.from_pool is None
    assert ticket_id.value is None
    assert allocator.calls == []


async def test_a_number_provided_on_create_is_kept_and_tracked_as_provided(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = _ticket_id(payload={"value": 7, "from_pool": {"id": POOL_ID}})

    await _apply_on_create(applier=applier, attribute=ticket_id)

    assert ticket_id.value == 7
    assert ticket_id.pool_provenance is PoolRecordProvenance.PROVIDED
    assert allocator.calls == [], "an attribute not saved yet is attached when the node is created"


async def test_a_number_provided_on_update_is_attached_to_the_pool(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = _ticket_id(payload={"value": 7, "from_pool": {"id": POOL_ID}}, saved=True)

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.value == 7
    assert ticket_id.pool_provenance is PoolRecordProvenance.PROVIDED
    assert allocator.calls == [PoolCall(action="attach", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id")]


async def test_the_pool_alone_on_a_number_no_pool_tracks_is_refused(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = _ticket_id(payload={"from_pool": {"id": POOL_ID}}, saved=True)
    ticket_id.value = 3
    ticket_id.is_default = False

    with pytest.raises(
        ValidationError,
        match=(
            r"^'ticket_id' already holds 3, so 'from_pool' alone is ambiguous\. Send the value together with 'from_pool' to "
            r"have the pool track it, or send 'value: null' with 'from_pool' to discard it and allocate a new "
            r"number\. at ticket_id\.from_pool$"
        ),
    ):
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)
    assert allocator.calls == []


async def test_naming_another_pool_with_a_null_value_moves_the_attribute_to_it(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, allocator: RecordingNumberAllocator
) -> None:
    finder.tracking_pool_ids[ATTRIBUTE_ID] = OTHER_POOL_ID
    ticket_id = _ticket_id(payload={"value": None, "from_pool": {"id": POOL_ID}}, saved=True)

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.value == 42
    assert ticket_id.pool_provenance is PoolRecordProvenance.ALLOCATED
    assert allocator.calls == [
        PoolCall(action="allocate", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id")
    ]


async def test_a_null_pool_on_a_tracked_number_releases_it_and_keeps_the_number(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, allocator: RecordingNumberAllocator
) -> None:
    finder.tracking_pool_ids[ATTRIBUTE_ID] = POOL_ID
    ticket_id = _ticket_id(payload={"from_pool": None}, saved=True)
    ticket_id.value = 3
    ticket_id.is_default = False

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.value == 3
    assert ticket_id.from_pool is None
    assert allocator.calls == [PoolCall(action="release", pool_id=None, node_id=NODE_ID, attribute_name="ticket_id")]


async def test_a_null_pool_on_a_number_no_pool_tracks_writes_nothing(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = _ticket_id(payload={"from_pool": None}, saved=True)
    ticket_id.value = 3
    ticket_id.is_default = False

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.value == 3
    assert allocator.calls == []


async def test_naming_another_pool_alone_over_a_held_number_is_refused(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, allocator: RecordingNumberAllocator
) -> None:
    finder.tracking_pool_ids[ATTRIBUTE_ID] = OTHER_POOL_ID
    ticket_id = _ticket_id(payload={"from_pool": {"id": POOL_ID}}, saved=True)
    ticket_id.value = 3
    ticket_id.is_default = False

    with pytest.raises(ValidationError, match=r"^'ticket_id' already holds 3, so 'from_pool' alone is ambiguous\. "):
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)
    assert allocator.calls == []


async def test_a_number_pool_attribute_draws_from_the_pool_its_schema_declares(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    attribute = _ticket_attribute(
        AttributeSchema(
            name="ticket_id", kind="NumberPool", parameters=NumberPoolParameters(number_pool_id=POOL_ID), optional=True
        )
    )

    await _apply_on_create(applier=applier, attribute=attribute)

    assert attribute.from_pool == {"id": POOL_ID}
    assert attribute.is_default is False
    assert attribute.value == 42
    assert allocator.calls == [
        PoolCall(action="allocate", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id")
    ]


async def test_a_number_pool_attribute_without_a_provisioned_pool_is_refused(applier: AttributePoolApplier) -> None:
    attribute = _ticket_attribute(
        AttributeSchema(name="ticket_id", kind="NumberPool", parameters=NumberPoolParameters(), optional=True)
    )

    with pytest.raises(ValidationError, match=r"^The pool for ticket_id has not been provisioned yet\. at ticket_id$"):
        await _apply_on_create(applier=applier, attribute=attribute)


async def test_from_pool_without_an_id_is_refused(applier: AttributePoolApplier) -> None:
    ticket_id = _ticket_id(payload={"from_pool": {"identifier": "no-id"}})

    with pytest.raises(ValidationError, match=r"^No pool ID specified in from_pool\. at ticket_id\.from_pool$"):
        await _apply_on_create(applier=applier, attribute=ticket_id)


async def test_an_unknown_pool_is_refused(applier: AttributePoolApplier) -> None:
    ticket_id = _ticket_id(payload={"from_pool": {"id": "no-such-pool"}})

    with pytest.raises(
        ValidationError,
        match=r"^The pool requested \{'id': 'no-such-pool'\} was not found\. at ticket_id\.from_pool$",
    ):
        await _apply_on_create(applier=applier, attribute=ticket_id)


async def test_a_pool_for_another_attribute_is_refused(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = _ticket_id(payload={"from_pool": {"id": OTHER_ATTRIBUTE_POOL_ID}})

    with pytest.raises(
        ValidationError, match=r"^The titles pool can't be used for 'ticket_id'\. at ticket_id\.from_pool$"
    ):
        await _apply_on_create(applier=applier, attribute=ticket_id)
    assert allocator.calls == []


async def test_an_exhausted_pool_is_reported_against_the_attribute(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = _ticket_id(payload={"from_pool": {"id": POOL_ID}})
    allocator.exhausted = True

    with pytest.raises(ValidationError) as exc_info:
        await _apply_on_create(applier=applier, attribute=ticket_id)
    assert exc_info.value.message == (
        f"Pool tickets ({POOL_ID}) has no free number left in its ranges. at ticket_id.from_pool"
    )
    assert ticket_id.value is None
