from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.attribute import Integer
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, PoolRecordProvenance
from infrahub.core.node import Node
from infrahub.core.query.resource_manager import TrackingPool
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import InitializationError, NodeNotFoundError, PoolExhaustedError, ValidationError
from infrahub.pools.attribute_pool_applier import AttributePoolApplier, LoadedNodePoolApplier
from infrahub.pools.intent import FromPoolIntentResolver
from infrahub.pools.number_ranges import PoolRange
from infrahub.pools.range_refusal import BranchValue

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
def range_reader() -> InMemoryPoolRangeReader:
    return InMemoryPoolRangeReader(
        ranges_by_pool_id={
            POOL_ID: [PoolRange(id="tickets-range", start=1, end=100)],
            OTHER_POOL_ID: [PoolRange(id="other-tickets-range", start=1, end=100)],
            OTHER_ATTRIBUTE_POOL_ID: [PoolRange(id="titles-range", start=1, end=100)],
        }
    )


@pytest.fixture
def branch_values() -> InMemoryAttributeBranchValues:
    return InMemoryAttributeBranchValues()


@pytest.fixture
def applier(
    finder: InMemoryNumberPoolFinder,
    allocator: RecordingNumberAllocator,
    range_reader: InMemoryPoolRangeReader,
    branch_values: InMemoryAttributeBranchValues,
) -> AttributePoolApplier:
    return AttributePoolApplier(
        pool_finder=finder,
        number_allocator=allocator,
        intent_resolver=FromPoolIntentResolver(),
        division_reader=UnscopedDivisionReader(),
        range_reader=range_reader,
        branch_values_reader=branch_values,
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
    assert ticket_id.tracking_pool == TrackingPool(pool_id=POOL_ID, provenance=PoolRecordProvenance.ALLOCATED)
    assert allocator.calls == [
        PoolCall(
            action="allocate", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id", reuse_reservation=False
        )
    ]


async def test_the_account_making_the_write_reaches_the_allocator(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = _ticket_id(payload={"from_pool": {"id": POOL_ID}})

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=OTHER_ACTOR_ID)

    assert allocator.calls == [
        PoolCall(
            action="allocate",
            pool_id=POOL_ID,
            node_id=NODE_ID,
            attribute_name="ticket_id",
            user_id=OTHER_ACTOR_ID,
            reuse_reservation=False,
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
    assert ticket_id.tracking_pool == TrackingPool(pool_id=POOL_ID, provenance=PoolRecordProvenance.PROVIDED)
    assert allocator.calls == [], "an attribute not saved yet is attached when the node is created"


async def test_a_number_provided_on_update_is_attached_to_the_pool(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = _ticket_id(payload={"value": 7, "from_pool": {"id": POOL_ID}}, saved=True)

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.value == 7
    assert ticket_id.tracking_pool == TrackingPool(pool_id=POOL_ID, provenance=PoolRecordProvenance.PROVIDED)
    assert allocator.calls == [PoolCall(action="attach", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id")]


async def test_a_number_the_pool_reports_as_allocated_stays_allocated_when_attached(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, allocator: RecordingNumberAllocator
) -> None:
    finder.tracking_pool_ids[ATTRIBUTE_ID] = POOL_ID
    allocator.attach_provenance = PoolRecordProvenance.ALLOCATED
    ticket_id = _ticket_id(payload={"value": 7, "from_pool": {"id": POOL_ID}}, saved=True)

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.tracking_pool == TrackingPool(pool_id=POOL_ID, provenance=PoolRecordProvenance.ALLOCATED)
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
    assert ticket_id.tracking_pool == TrackingPool(pool_id=POOL_ID, provenance=PoolRecordProvenance.ALLOCATED)
    assert allocator.calls == [
        PoolCall(
            action="allocate", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id", reuse_reservation=False
        )
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
    assert ticket_id.tracking_pool is None
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
        PoolCall(
            action="allocate", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id", reuse_reservation=True
        )
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


def _untracked_attach_message(ranges: str, value: int = 900) -> str:
    return (
        f"The tickets pool cannot track {value} on 'ticket_id', because {value} is outside its ranges: {ranges}. "
        f"Send a number inside those ranges. at ticket_id.from_pool"
    )


async def test_a_number_outside_the_ranges_is_refused_on_create(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = _ticket_id(payload={"value": 900, "from_pool": {"id": POOL_ID}})

    with pytest.raises(ValidationError) as exc_info:
        await _apply_on_create(applier=applier, attribute=ticket_id)

    assert exc_info.value.message == _untracked_attach_message(ranges="1-100")
    assert ticket_id.tracking_pool is None
    assert allocator.calls == []


async def test_moving_a_number_to_a_pool_whose_ranges_exclude_it_is_refused(
    applier: AttributePoolApplier,
    finder: InMemoryNumberPoolFinder,
    range_reader: InMemoryPoolRangeReader,
    allocator: RecordingNumberAllocator,
) -> None:
    finder.tracking_pool_ids[ATTRIBUTE_ID] = OTHER_POOL_ID
    range_reader.ranges_by_pool_id[POOL_ID] = [PoolRange(id="tickets-range", start=1, end=40)]
    ticket_id = _ticket_id(payload={"value": 50, "from_pool": {"id": POOL_ID}}, saved=True)

    with pytest.raises(ValidationError) as exc_info:
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert exc_info.value.message == _untracked_attach_message(ranges="1-40", value=50)
    assert allocator.calls == []


async def test_restating_the_tracking_pool_with_a_number_outside_its_ranges_is_refused(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, allocator: RecordingNumberAllocator
) -> None:
    finder.tracking_pool_ids[ATTRIBUTE_ID] = POOL_ID
    ticket_id = _ticket_id(payload={"value": 900, "from_pool": {"id": POOL_ID}}, saved=True)

    with pytest.raises(ValidationError) as exc_info:
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert exc_info.value.message == (
        "'ticket_id' is tracked by the tickets pool, so it cannot hold 900, which is outside the pool's ranges: "
        "1-100. To set 900 and stop the pool tracking 'ticket_id', send 'value: 900' together with "
        "'from_pool: null'. at ticket_id.from_pool"
    )
    assert allocator.calls == []


async def test_a_number_between_two_ranges_is_refused_and_every_range_is_listed(
    applier: AttributePoolApplier, range_reader: InMemoryPoolRangeReader, allocator: RecordingNumberAllocator
) -> None:
    range_reader.ranges_by_pool_id[POOL_ID] = [
        PoolRange(id="upper", start=20, end=30),
        PoolRange(id="lower", start=1, end=10),
    ]
    ticket_id = _ticket_id(payload={"value": 15, "from_pool": {"id": POOL_ID}}, saved=True)

    with pytest.raises(ValidationError) as exc_info:
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert exc_info.value.message == _untracked_attach_message(ranges="1-10, 20-30", value=15)
    assert allocator.calls == []


async def test_a_number_inside_the_second_of_two_ranges_is_attached(
    applier: AttributePoolApplier, range_reader: InMemoryPoolRangeReader, allocator: RecordingNumberAllocator
) -> None:
    range_reader.ranges_by_pool_id[POOL_ID] = [
        PoolRange(id="lower", start=1, end=10),
        PoolRange(id="upper", start=20, end=30),
    ]
    ticket_id = _ticket_id(payload={"value": 30, "from_pool": {"id": POOL_ID}}, saved=True)

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.tracking_pool == TrackingPool(pool_id=POOL_ID, provenance=PoolRecordProvenance.PROVIDED)
    assert allocator.calls == [PoolCall(action="attach", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id")]


async def test_a_pool_without_ranges_refuses_every_number(
    applier: AttributePoolApplier, range_reader: InMemoryPoolRangeReader, allocator: RecordingNumberAllocator
) -> None:
    range_reader.ranges_by_pool_id[POOL_ID] = []
    ticket_id = _ticket_id(payload={"value": 1, "from_pool": {"id": POOL_ID}})

    with pytest.raises(ValidationError) as exc_info:
        await _apply_on_create(applier=applier, attribute=ticket_id)

    assert exc_info.value.message == _untracked_attach_message(ranges="no ranges", value=1)
    assert allocator.calls == []


async def test_a_number_outside_the_ranges_sent_with_a_null_pool_is_released_and_kept(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, allocator: RecordingNumberAllocator
) -> None:
    finder.tracking_pool_ids[ATTRIBUTE_ID] = POOL_ID
    ticket_id = _ticket_id(payload={"value": 900, "from_pool": None}, saved=True)

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.value == 900
    assert ticket_id.tracking_pool is None
    assert allocator.calls == [PoolCall(action="release", pool_id=None, node_id=NODE_ID, attribute_name="ticket_id")]


def _other_branch_message(held: str) -> str:
    return (
        f"The tickets pool cannot track 'ticket_id', because a pool tracks an attribute on every branch and {held} "
        "outside its ranges: 1-100. Change the number on that branch, or delete the branch, before attaching. "
        "at ticket_id.from_pool"
    )


def _held(branch: str, value: int) -> BranchValue:
    return BranchValue(attribute_id=ATTRIBUTE_ID, branch=branch, value=value)


@dataclass
class OtherBranchRefusalCase:
    name: str
    tracking_pool_id: str | None


@pytest.mark.parametrize(
    "case",
    [
        OtherBranchRefusalCase(name="tracked-by-no-pool", tracking_pool_id=None),
        OtherBranchRefusalCase(name="tracked-by-another-pool", tracking_pool_id=OTHER_POOL_ID),
    ],
    ids=lambda case: case.name,
)
async def test_an_attach_is_refused_when_another_branch_holds_a_number_outside_the_ranges(
    applier: AttributePoolApplier,
    finder: InMemoryNumberPoolFinder,
    branch_values: InMemoryAttributeBranchValues,
    allocator: RecordingNumberAllocator,
    case: OtherBranchRefusalCase,
) -> None:
    if case.tracking_pool_id is not None:
        finder.tracking_pool_ids[ATTRIBUTE_ID] = case.tracking_pool_id
    branch_values.values = [_held(branch="main", value=5), _held(branch="old", value=900), _held("feature", 950)]
    ticket_id = _ticket_id(payload={"value": 5, "from_pool": {"id": POOL_ID}}, saved=True)

    with pytest.raises(ValidationError) as exc_info:
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert exc_info.value.message == _other_branch_message(held="branch 'feature' holds 950, branch 'old' holds 900")
    assert branch_values.reads == [[ATTRIBUTE_ID]]
    assert allocator.calls == []


@dataclass
class OtherBranchAttachCase:
    name: str
    held: list[BranchValue]


@pytest.mark.parametrize(
    "case",
    [
        OtherBranchAttachCase(name="only-the-writing-branch-holds-a-number-outside", held=[_held("main", 900)]),
        OtherBranchAttachCase(
            name="a-branch-agnostic-number-the-write-replaces-is-outside", held=[_held("-global-", 900)]
        ),
        OtherBranchAttachCase(name="another-branch-holds-a-number-inside", held=[_held("main", 900), _held("f", 70)]),
        OtherBranchAttachCase(name="no-other-branch-holds-a-number", held=[]),
    ],
    ids=lambda case: case.name,
)
async def test_an_attach_proceeds_when_no_other_branch_holds_a_number_outside_the_ranges(
    applier: AttributePoolApplier,
    branch_values: InMemoryAttributeBranchValues,
    allocator: RecordingNumberAllocator,
    case: OtherBranchAttachCase,
) -> None:
    branch_values.values = case.held
    ticket_id = _ticket_id(payload={"value": 5, "from_pool": {"id": POOL_ID}}, saved=True)

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.tracking_pool == TrackingPool(pool_id=POOL_ID, provenance=PoolRecordProvenance.PROVIDED)
    assert branch_values.reads == [[ATTRIBUTE_ID]]
    assert allocator.calls == [PoolCall(action="attach", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id")]


async def test_restating_the_tracking_pool_reads_no_other_branch(
    applier: AttributePoolApplier,
    finder: InMemoryNumberPoolFinder,
    branch_values: InMemoryAttributeBranchValues,
    allocator: RecordingNumberAllocator,
) -> None:
    finder.tracking_pool_ids[ATTRIBUTE_ID] = POOL_ID
    branch_values.values = [_held("old", 900)]
    ticket_id = _ticket_id(payload={"value": 5, "from_pool": {"id": POOL_ID}}, saved=True)

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert branch_values.reads == []
    assert allocator.calls == [PoolCall(action="attach", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id")]


async def test_an_attach_on_create_reads_no_other_branch(
    applier: AttributePoolApplier, branch_values: InMemoryAttributeBranchValues
) -> None:
    ticket_id = _ticket_id(payload={"value": 5, "from_pool": {"id": POOL_ID}})

    await _apply_on_create(applier=applier, attribute=ticket_id)

    assert ticket_id.tracking_pool == TrackingPool(pool_id=POOL_ID, provenance=PoolRecordProvenance.PROVIDED)
    assert branch_values.reads == []


async def test_a_number_sent_outside_the_ranges_is_refused_before_other_branches_are_read(
    applier: AttributePoolApplier, branch_values: InMemoryAttributeBranchValues
) -> None:
    branch_values.values = [_held("old", 950)]
    ticket_id = _ticket_id(payload={"value": 900, "from_pool": {"id": POOL_ID}}, saved=True)

    with pytest.raises(ValidationError) as exc_info:
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert exc_info.value.message == _untracked_attach_message(ranges="1-100")
    assert branch_values.reads == []


def _edited_ticket_id(value: int | None, tracking_pool_id: str | None) -> BaseAttribute:
    """Build a saved ticket attribute loaded with the pool tracking it, then given `value` alone by a write."""
    ticket_id = _ticket_id(payload={"value": value}, saved=True)
    ticket_id.tracking_pool = (
        TrackingPool(pool_id=tracking_pool_id, provenance=PoolRecordProvenance.PROVIDED)
        if tracking_pool_id is not None
        else None
    )
    return ticket_id


async def test_editing_a_tracked_number_to_one_outside_the_ranges_is_refused(
    applier: AttributePoolApplier, range_reader: InMemoryPoolRangeReader
) -> None:
    ticket_id = _edited_ticket_id(value=900, tracking_pool_id=POOL_ID)

    with pytest.raises(ValidationError) as exc_info:
        await applier.check_value_change(node=ticket_id.node, attribute=ticket_id)

    assert exc_info.value.message == (
        "'ticket_id' is tracked by the tickets pool, so it cannot hold 900, which is outside the pool's ranges: "
        "1-100. To set 900 and stop the pool tracking 'ticket_id', send 'value: 900' together with "
        "'from_pool: null'. at ticket_id.value"
    )
    assert range_reader.reads == [POOL_ID]


async def test_editing_a_tracked_number_to_one_inside_the_ranges_is_allowed(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, range_reader: InMemoryPoolRangeReader
) -> None:
    ticket_id = _edited_ticket_id(value=60, tracking_pool_id=POOL_ID)

    await applier.check_value_change(node=ticket_id.node, attribute=ticket_id)

    assert ticket_id.value == 60
    assert ticket_id.tracking_pool == TrackingPool(pool_id=POOL_ID, provenance=PoolRecordProvenance.PROVIDED)
    assert range_reader.reads == [POOL_ID]
    assert finder.tracking_pool_lookups == []


async def test_editing_a_number_no_pool_tracks_reads_nothing(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, range_reader: InMemoryPoolRangeReader
) -> None:
    ticket_id = _edited_ticket_id(value=900, tracking_pool_id=None)

    await applier.check_value_change(node=ticket_id.node, attribute=ticket_id)

    assert ticket_id.value == 900
    assert finder.tracking_pool_lookups == []
    assert range_reader.reads == []


async def test_emptying_a_number_no_pool_tracks_reads_nothing(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, range_reader: InMemoryPoolRangeReader
) -> None:
    ticket_id = _edited_ticket_id(value=None, tracking_pool_id=None)

    await applier.check_value_change(node=ticket_id.node, attribute=ticket_id)

    assert ticket_id.value is None
    assert finder.tracking_pool_lookups == []
    assert range_reader.reads == []


async def test_a_number_loaded_without_the_pool_tracking_it_cannot_be_checked(
    applier: AttributePoolApplier, range_reader: InMemoryPoolRangeReader
) -> None:
    ticket_id = _ticket_id(payload={"value": 900}, saved=True)

    with pytest.raises(
        InitializationError,
        match=rf"^'ticket_id' of {NODE_ID} was loaded without the pool tracking it, so it cannot be checked$",
    ):
        await applier.check_value_change(node=ticket_id.node, attribute=ticket_id)
    assert range_reader.reads == []


async def test_a_loaded_node_cannot_check_a_number_against_a_pool() -> None:
    ticket_id = _ticket_id(payload={"value": 50}, saved=True)

    with pytest.raises(
        InitializationError,
        match=rf"^The loaded node {NODE_ID} cannot check 'ticket_id' against the pool tracking it$",
    ):
        await LoadedNodePoolApplier().check_value_change(node=ticket_id.node, attribute=ticket_id)
