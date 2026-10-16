from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import PoolRecordProvenance
from infrahub.core.query.resource_manager import TrackingPool
from infrahub.exceptions import InitializationError, ValidationError
from infrahub.pools.attribute_pool_applier import AttributePoolApplier, LoadedNodePoolApplier
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
    make_ticket_id,
)

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute


def _edited_ticket_id(value: int | None, tracking_pool_id: str | None) -> BaseAttribute:
    """Build a saved ticket attribute loaded with the pool tracking it, then given `value` alone by a write."""
    ticket_id = make_ticket_id(payload={"value": value}, saved=True)
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


async def test_emptying_a_tracked_number_is_refused_without_reading_the_ranges(
    applier: AttributePoolApplier, range_reader: InMemoryPoolRangeReader
) -> None:
    ticket_id = _edited_ticket_id(value=None, tracking_pool_id=POOL_ID)

    with pytest.raises(ValidationError) as exc_info:
        await applier.check_value_change(node=ticket_id.node, attribute=ticket_id)

    assert exc_info.value.message == (
        "'ticket_id' is tracked by the tickets pool, so it cannot be emptied. To empty 'ticket_id' and stop the pool "
        "tracking it, send 'value: null' together with 'from_pool: null'. at ticket_id.value"
    )
    assert range_reader.reads == []


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
    ticket_id = make_ticket_id(payload={"value": 900}, saved=True)

    with pytest.raises(
        InitializationError,
        match=rf"^'ticket_id' of {NODE_ID} was loaded without the pool tracking it, so it cannot be checked$",
    ):
        await applier.check_value_change(node=ticket_id.node, attribute=ticket_id)
    assert range_reader.reads == []


def _reset_ticket_id(tracking_pool_id: str | None) -> BaseAttribute:
    """Build a saved ticket attribute loaded with the pool tracking it, then given `is_default: true` alone by a write."""
    ticket_id = make_ticket_id(payload={"value": 50}, saved=True)
    ticket_id.tracking_pool = (
        TrackingPool(pool_id=tracking_pool_id, provenance=PoolRecordProvenance.PROVIDED)
        if tracking_pool_id is not None
        else None
    )
    ticket_id.is_default = True
    ticket_id.set_default_value()
    return ticket_id


async def test_resetting_a_tracked_number_to_its_default_is_refused_without_reading_the_ranges(
    applier: AttributePoolApplier, range_reader: InMemoryPoolRangeReader, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = _reset_ticket_id(tracking_pool_id=POOL_ID)

    with pytest.raises(ValidationError) as exc_info:
        await applier.check_reset_to_default(node=ticket_id.node, attribute=ticket_id)

    assert exc_info.value.message == (
        "'ticket_id' is tracked by the tickets pool, so it cannot be reset to its default. To reset 'ticket_id' and "
        "stop the pool tracking it, send 'is_default: true' together with 'from_pool: null'. at ticket_id.is_default"
    )
    assert range_reader.reads == []
    assert allocator.calls == []


async def test_resetting_a_number_no_pool_tracks_reads_nothing(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, range_reader: InMemoryPoolRangeReader
) -> None:
    ticket_id = _reset_ticket_id(tracking_pool_id=None)

    await applier.check_reset_to_default(node=ticket_id.node, attribute=ticket_id)

    assert ticket_id.is_default is True
    assert ticket_id.value is None
    assert finder.tracking_pool_lookups == []
    assert range_reader.reads == []


async def test_a_reset_loaded_without_the_pool_tracking_it_cannot_be_checked(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder
) -> None:
    ticket_id = make_ticket_id(payload={"value": 50}, saved=True)

    with pytest.raises(
        InitializationError,
        match=rf"^'ticket_id' of {NODE_ID} was loaded without the pool tracking it, so it cannot be checked$",
    ):
        await applier.check_reset_to_default(node=ticket_id.node, attribute=ticket_id)
    assert finder.tracking_pool_lookups == []


async def test_a_loaded_node_cannot_check_a_reset_against_a_pool() -> None:
    ticket_id = make_ticket_id(payload={"value": 50}, saved=True)

    with pytest.raises(
        InitializationError,
        match=rf"^The loaded node {NODE_ID} cannot check a reset of 'ticket_id' against the pool tracking it$",
    ):
        await LoadedNodePoolApplier().check_reset_to_default(node=ticket_id.node, attribute=ticket_id)


async def test_a_loaded_node_cannot_check_a_number_against_a_pool() -> None:
    ticket_id = make_ticket_id(payload={"value": 50}, saved=True)

    with pytest.raises(
        InitializationError,
        match=rf"^The loaded node {NODE_ID} cannot check 'ticket_id' against the pool tracking it$",
    ):
        await LoadedNodePoolApplier().check_value_change(node=ticket_id.node, attribute=ticket_id)


async def _ticket_id_written_with(payload: dict[str, Any]) -> BaseAttribute:
    """Build a saved ticket attribute holding 50, then apply `payload` to it as an update would."""
    ticket_id = make_ticket_id(payload={"value": 50}, saved=True)
    ticket_id.is_default = False
    await ticket_id.from_graphql(data=payload)
    return ticket_id


async def test_a_reset_naming_the_pool_tracking_the_number_is_refused(
    applier: AttributePoolApplier,
    finder: InMemoryNumberPoolFinder,
    range_reader: InMemoryPoolRangeReader,
    allocator: RecordingNumberAllocator,
) -> None:
    finder.tracking_pool_ids[ATTRIBUTE_ID] = POOL_ID
    ticket_id = await _ticket_id_written_with(payload={"is_default": True, "from_pool": {"id": "tickets"}})

    with pytest.raises(ValidationError) as exc_info:
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert exc_info.value.message == (
        "'ticket_id' is tracked by the tickets pool, so it cannot be reset to its default. To reset 'ticket_id' and "
        "stop the pool tracking it, send 'is_default: true' together with 'from_pool: null'. at ticket_id.is_default"
    )
    assert range_reader.reads == []
    assert allocator.calls == []


async def test_a_reset_naming_another_pool_allocates_from_it(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, allocator: RecordingNumberAllocator
) -> None:
    finder.tracking_pool_ids[ATTRIBUTE_ID] = OTHER_POOL_ID
    ticket_id = await _ticket_id_written_with(payload={"is_default": True, "from_pool": {"id": POOL_ID}})

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.value == 42
    assert ticket_id.tracking_pool == TrackingPool(pool_id=POOL_ID, provenance=PoolRecordProvenance.ALLOCATED)
    assert allocator.calls == [
        PoolCall(
            action="allocate", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id", reuse_reservation=False
        )
    ]


async def test_a_reset_with_a_null_pool_releases_the_tracked_number(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, allocator: RecordingNumberAllocator
) -> None:
    finder.tracking_pool_ids[ATTRIBUTE_ID] = POOL_ID
    ticket_id = await _ticket_id_written_with(payload={"is_default": True, "from_pool": None})

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.is_default is True
    assert ticket_id.value is None
    assert ticket_id.tracking_pool is None
    assert allocator.calls == [PoolCall(action="release", pool_id=None, node_id=NODE_ID, attribute_name="ticket_id")]
