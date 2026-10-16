from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import PoolRecordProvenance
from infrahub.core.query.resource_manager import TrackingPool
from infrahub.exceptions import ValidationError
from infrahub.pools.range_refusal import BranchValue
from tests.unit.pools.attribute_pool_applier.helpers import (
    ACTOR_ID,
    ATTRIBUTE_ID,
    NODE_ID,
    OTHER_POOL_ID,
    POOL_ID,
    InMemoryAttributeBranchValues,
    InMemoryNumberPoolFinder,
    PoolCall,
    RecordingNumberAllocator,
    apply_on_create,
    make_ticket_id,
    untracked_attach_message,
)

if TYPE_CHECKING:
    from infrahub.pools.attribute_pool_applier import AttributePoolApplier


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
    ticket_id = make_ticket_id(payload={"value": 5, "from_pool": {"id": POOL_ID}}, saved=True)

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
    ticket_id = make_ticket_id(payload={"value": 5, "from_pool": {"id": POOL_ID}}, saved=True)

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
    ticket_id = make_ticket_id(payload={"value": 5, "from_pool": {"id": POOL_ID}}, saved=True)

    await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert branch_values.reads == []
    assert allocator.calls == [PoolCall(action="attach", pool_id=POOL_ID, node_id=NODE_ID, attribute_name="ticket_id")]


async def test_an_attach_on_create_reads_no_other_branch(
    applier: AttributePoolApplier, branch_values: InMemoryAttributeBranchValues
) -> None:
    ticket_id = make_ticket_id(payload={"value": 5, "from_pool": {"id": POOL_ID}})

    await apply_on_create(applier=applier, attribute=ticket_id)

    assert ticket_id.tracking_pool == TrackingPool(pool_id=POOL_ID, provenance=PoolRecordProvenance.PROVIDED)
    assert branch_values.reads == []


async def test_a_number_sent_outside_the_ranges_is_refused_before_other_branches_are_read(
    applier: AttributePoolApplier, branch_values: InMemoryAttributeBranchValues
) -> None:
    branch_values.values = [_held("old", 950)]
    ticket_id = make_ticket_id(payload={"value": 900, "from_pool": {"id": POOL_ID}}, saved=True)

    with pytest.raises(ValidationError) as exc_info:
        await applier.apply(node=ticket_id.node, attribute=ticket_id, allocate=True, user_id=ACTOR_ID)

    assert exc_info.value.message == untracked_attach_message(ranges="1-100")
    assert branch_values.reads == []
