from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import PoolRecordProvenance
from infrahub.core.query.resource_manager import TrackingPool
from infrahub.core.schema import AttributeSchema
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.exceptions import ValidationError
from tests.unit.pools.attribute_pool_applier.helpers import (
    ACTOR_ID,
    ATTRIBUTE_ID,
    NODE_ID,
    OTHER_ACTOR_ID,
    OTHER_ATTRIBUTE_POOL_ID,
    OTHER_POOL_ID,
    POOL_ID,
    InMemoryNumberPoolFinder,
    PoolCall,
    RecordingNumberAllocator,
    apply_on_create,
    make_ticket_attribute,
    make_ticket_id,
)

if TYPE_CHECKING:
    from infrahub.pools.attribute_pool_applier import AttributePoolApplier


async def test_pool_named_by_id_gives_the_attribute_its_number(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = make_ticket_id(payload={"from_pool": {"id": POOL_ID}})

    await apply_on_create(applier=applier, attribute=ticket_id)

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
    ticket_id = make_ticket_id(payload={"from_pool": {"id": POOL_ID}})

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
    ticket_id = make_ticket_id(payload={"from_pool": {"id": "tickets"}})

    await apply_on_create(applier=applier, attribute=ticket_id)

    assert ticket_id.from_pool == {"id": POOL_ID}
    assert ticket_id.value == 42


async def test_without_allocation_only_the_pool_is_resolved(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = make_ticket_id(payload={"from_pool": {"id": "tickets"}})

    await apply_on_create(applier=applier, attribute=ticket_id, allocate=False)

    assert ticket_id.from_pool == {"id": POOL_ID}
    assert ticket_id.value is None
    assert allocator.calls == []


async def test_an_attribute_naming_no_pool_is_left_alone(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = make_ticket_id()

    await apply_on_create(applier=applier, attribute=ticket_id)

    assert ticket_id.from_pool is None
    assert ticket_id.value is None
    assert allocator.calls == []


async def test_a_number_provided_on_create_is_kept_and_tracked_as_provided(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = make_ticket_id(payload={"value": 7, "from_pool": {"id": POOL_ID}})

    await apply_on_create(applier=applier, attribute=ticket_id)

    assert ticket_id.value == 7
    assert ticket_id.tracking_pool == TrackingPool(pool_id=POOL_ID, provenance=PoolRecordProvenance.PROVIDED)
    assert allocator.calls == [], "an attribute not saved yet is attached when the node is created"


async def test_a_number_provided_on_update_is_attached_to_the_pool(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = make_ticket_id(payload={"value": 7, "from_pool": {"id": POOL_ID}}, saved=True)

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.value == 7
    assert ticket_id.tracking_pool == TrackingPool(pool_id=POOL_ID, provenance=PoolRecordProvenance.PROVIDED)
    assert allocator.calls == [PoolCall(action="attach", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id")]


async def test_a_number_the_pool_reports_as_allocated_stays_allocated_when_attached(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, allocator: RecordingNumberAllocator
) -> None:
    finder.tracking_pool_ids[ATTRIBUTE_ID] = POOL_ID
    allocator.attach_provenance = PoolRecordProvenance.ALLOCATED
    ticket_id = make_ticket_id(payload={"value": 7, "from_pool": {"id": POOL_ID}}, saved=True)

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.tracking_pool == TrackingPool(pool_id=POOL_ID, provenance=PoolRecordProvenance.ALLOCATED)
    assert allocator.calls == [PoolCall(action="attach", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id")]


async def test_the_pool_alone_on_a_number_no_pool_tracks_is_refused(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = make_ticket_id(payload={"from_pool": {"id": POOL_ID}}, saved=True)
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
    ticket_id = make_ticket_id(payload={"value": None, "from_pool": {"id": POOL_ID}}, saved=True)

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
    ticket_id = make_ticket_id(payload={"from_pool": None}, saved=True)
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
    ticket_id = make_ticket_id(payload={"from_pool": None}, saved=True)
    ticket_id.value = 3
    ticket_id.is_default = False

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert ticket_id.value == 3
    assert allocator.calls == []


async def test_naming_another_pool_alone_over_a_held_number_is_refused(
    applier: AttributePoolApplier, finder: InMemoryNumberPoolFinder, allocator: RecordingNumberAllocator
) -> None:
    finder.tracking_pool_ids[ATTRIBUTE_ID] = OTHER_POOL_ID
    ticket_id = make_ticket_id(payload={"from_pool": {"id": POOL_ID}}, saved=True)
    ticket_id.value = 3
    ticket_id.is_default = False

    with pytest.raises(ValidationError, match=r"^'ticket_id' already holds 3, so 'from_pool' alone is ambiguous\. "):
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)
    assert allocator.calls == []


async def test_a_number_pool_attribute_draws_from_the_pool_its_schema_declares(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    attribute = make_ticket_attribute(
        AttributeSchema(
            name="ticket_id", kind="NumberPool", parameters=NumberPoolParameters(number_pool_id=POOL_ID), optional=True
        )
    )

    await apply_on_create(applier=applier, attribute=attribute)

    assert attribute.from_pool == {"id": POOL_ID}
    assert attribute.is_default is False
    assert attribute.value == 42
    assert allocator.calls == [
        PoolCall(
            action="allocate", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id", reuse_reservation=True
        )
    ]


async def test_a_number_pool_attribute_without_a_provisioned_pool_is_refused(applier: AttributePoolApplier) -> None:
    attribute = make_ticket_attribute(
        AttributeSchema(name="ticket_id", kind="NumberPool", parameters=NumberPoolParameters(), optional=True)
    )

    with pytest.raises(ValidationError, match=r"^The pool for ticket_id has not been provisioned yet\. at ticket_id$"):
        await apply_on_create(applier=applier, attribute=attribute)


async def test_from_pool_without_an_id_is_refused(applier: AttributePoolApplier) -> None:
    ticket_id = make_ticket_id(payload={"from_pool": {"identifier": "no-id"}})

    with pytest.raises(ValidationError, match=r"^No pool ID specified in from_pool\. at ticket_id\.from_pool$"):
        await apply_on_create(applier=applier, attribute=ticket_id)


async def test_an_unknown_pool_is_refused(applier: AttributePoolApplier) -> None:
    ticket_id = make_ticket_id(payload={"from_pool": {"id": "no-such-pool"}})

    with pytest.raises(
        ValidationError,
        match=r"^The pool requested \{'id': 'no-such-pool'\} was not found\. at ticket_id\.from_pool$",
    ):
        await apply_on_create(applier=applier, attribute=ticket_id)


async def test_a_pool_for_another_attribute_is_refused(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = make_ticket_id(payload={"from_pool": {"id": OTHER_ATTRIBUTE_POOL_ID}})

    with pytest.raises(
        ValidationError, match=r"^The titles pool can't be used for 'ticket_id'\. at ticket_id\.from_pool$"
    ):
        await apply_on_create(applier=applier, attribute=ticket_id)
    assert allocator.calls == []


async def test_an_exhausted_pool_is_reported_against_the_attribute(
    applier: AttributePoolApplier, allocator: RecordingNumberAllocator
) -> None:
    ticket_id = make_ticket_id(payload={"from_pool": {"id": POOL_ID}})
    allocator.exhausted = True

    with pytest.raises(ValidationError) as exc_info:
        await apply_on_create(applier=applier, attribute=ticket_id)
    assert exc_info.value.message == (
        f"Pool tickets ({POOL_ID}) has no free number left in its ranges. at ticket_id.from_pool"
    )
    assert ticket_id.value is None
