from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import PoolRecordProvenance
from infrahub.core.query.resource_manager import TrackingPool
from infrahub.exceptions import ValidationError
from infrahub.pools.number_ranges import PoolRange
from tests.unit.pools.attribute_pool_applier.helpers import (
    ACTOR_ID,
    ATTRIBUTE_ID,
    NODE_ID,
    OTHER_POOL_ID,
    POOL_ID,
    InMemoryNumberPoolFinder,
    InMemoryPoolRangeReader,
    PoolCall,
    RecordingNumberAllocator,
    apply_on_create,
    make_ticket_id,
    untracked_attach_message,
)

if TYPE_CHECKING:
    from infrahub.pools.attribute_pool_applier import AttributePoolApplier


async def test_a_number_outside_the_ranges_is_refused_on_create(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = make_ticket_id(payload={"value": 900, "from_pool": {"id": POOL_ID}})

    with pytest.raises(ValidationError) as exc_info:
        await apply_on_create(applier=applier, attribute=ticket_id)

    assert exc_info.value.message == untracked_attach_message(ranges="1-100")
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
    ticket_id = make_ticket_id(payload={"value": 50, "from_pool": {"id": POOL_ID}}, saved=True)

    with pytest.raises(ValidationError) as exc_info:
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert exc_info.value.message == untracked_attach_message(ranges="1-40", value=50)
    assert allocator.calls == []


async def test_restating_the_tracking_pool_with_a_number_outside_its_ranges_is_refused(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, allocator: RecordingNumberAllocator
) -> None:
    finder.tracking_pool_ids[ATTRIBUTE_ID] = POOL_ID
    ticket_id = make_ticket_id(payload={"value": 900, "from_pool": {"id": POOL_ID}}, saved=True)

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
    ticket_id = make_ticket_id(payload={"value": 15, "from_pool": {"id": POOL_ID}}, saved=True)

    with pytest.raises(ValidationError) as exc_info:
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert exc_info.value.message == untracked_attach_message(ranges="1-10, 20-30", value=15)
    assert allocator.calls == []


async def test_a_number_inside_the_second_of_two_ranges_is_attached(
    applier: AttributePoolApplier, range_reader: InMemoryPoolRangeReader, allocator: RecordingNumberAllocator
) -> None:
    range_reader.ranges_by_pool_id[POOL_ID] = [
        PoolRange(id="lower", start=1, end=10),
        PoolRange(id="upper", start=20, end=30),
    ]
    ticket_id = make_ticket_id(payload={"value": 30, "from_pool": {"id": POOL_ID}}, saved=True)

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.tracking_pool == TrackingPool(pool_id=POOL_ID, provenance=PoolRecordProvenance.PROVIDED)
    assert allocator.calls == [PoolCall(action="attach", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id")]


async def test_a_pool_without_ranges_refuses_every_number(
    applier: AttributePoolApplier, range_reader: InMemoryPoolRangeReader, allocator: RecordingNumberAllocator
) -> None:
    range_reader.ranges_by_pool_id[POOL_ID] = []
    ticket_id = make_ticket_id(payload={"value": 1, "from_pool": {"id": POOL_ID}})

    with pytest.raises(ValidationError) as exc_info:
        await apply_on_create(applier=applier, attribute=ticket_id)

    assert exc_info.value.message == untracked_attach_message(ranges="no ranges", value=1)
    assert allocator.calls == []


async def test_a_number_outside_the_ranges_sent_with_a_null_pool_is_released_and_kept(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, allocator: RecordingNumberAllocator
) -> None:
    finder.tracking_pool_ids[ATTRIBUTE_ID] = POOL_ID
    ticket_id = make_ticket_id(payload={"value": 900, "from_pool": None}, saved=True)

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.value == 900
    assert ticket_id.tracking_pool is None
    assert allocator.calls == [PoolCall(action="release", pool_id=None, node_id=NODE_ID, attribute_name="ticket_id")]
