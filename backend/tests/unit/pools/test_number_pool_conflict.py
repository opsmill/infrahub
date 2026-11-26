from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from infrahub.core.attribute import Integer
from infrahub.core.branch import Branch
from infrahub.core.constants import PoolRecordProvenance
from infrahub.core.node import Node
from infrahub.core.query.resource_manager import TrackingPool
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from infrahub.core.timestamp import Timestamp
from infrahub.pools.number_pool_conflict import NumberPoolConflictFinder, PooledNumber, PooledNumberConflict
from infrahub.pools.number_pool_usage import NumberHolder

if TYPE_CHECKING:
    from collections.abc import Sequence

BRANCH = Branch(name="main")
POOL_NAMES = {"pool-racks": "racks", "pool-slots": "slots", "pool-legacy-racks": "legacy-racks"}


@dataclass
class InMemoryPoolNames:
    names: dict[str, str]

    async def get_pool_name(self, pool_id: str) -> str | None:
        return self.names.get(pool_id)


@dataclass(frozen=True)
class HolderRead:
    node_id: str
    attribute_names: tuple[str, ...]


@dataclass
class InMemoryHolders:
    holders: dict[str, NumberHolder]
    reads: list[HolderRead] = field(default_factory=list)

    async def read(self, node_id: str, attribute_names: Sequence[str], branch: Branch) -> NumberHolder | None:
        self.reads.append(HolderRead(node_id=node_id, attribute_names=tuple(attribute_names)))
        return self.holders.get(node_id)


@dataclass(frozen=True)
class FieldState:
    value: int
    tracking_pool: TrackingPool | None = None


def allocated(pool_id: str) -> TrackingPool:
    return TrackingPool(pool_id=pool_id, provenance=PoolRecordProvenance.ALLOCATED)


def slot_node(rack: FieldState, slot: FieldState) -> Node:
    """Build a slot as a create would leave it, before the uniqueness check runs."""
    at = Timestamp()
    schema = NodeSchema(
        name="Slot",
        namespace="Testing",
        attributes=[
            AttributeSchema(name="rack", kind="Number", optional=True),
            AttributeSchema(name="slot", kind="Number", optional=True),
        ],
        relationships=[RelationshipSchema(name="site", peer="TestingSite", optional=True)],
    )
    node = Node(schema=schema, branch=BRANCH, at=at)
    for attribute_schema, state in zip(schema.attributes, (rack, slot), strict=True):
        attribute = Integer(name=attribute_schema.name, schema=attribute_schema, branch=BRANCH, at=at, node=node)
        attribute.value = state.value
        attribute.tracking_pool = state.tracking_pool
        setattr(node, attribute_schema.name, attribute)
    return node


@dataclass(frozen=True)
class FinderCase:
    name: str
    rack: FieldState
    slot: FieldState
    fields: tuple[str, ...]
    holders: dict[str, NumberHolder]
    expected: PooledNumberConflict | None
    expected_reads: tuple[HolderRead, ...]


FINDER_CASES = [
    FinderCase(
        name="a_number_set_by_hand_is_not_a_pool_conflict",
        rack=FieldState(value=1),
        slot=FieldState(value=21),
        fields=("rack", "slot"),
        holders={},
        expected=None,
        expected_reads=(),
    ),
    FinderCase(
        name="a_number_provided_to_a_pool_is_not_a_pool_conflict",
        rack=FieldState(
            value=1, tracking_pool=TrackingPool(pool_id="pool-racks", provenance=PoolRecordProvenance.PROVIDED)
        ),
        slot=FieldState(value=21),
        fields=("rack",),
        holders={},
        expected=None,
        expected_reads=(),
    ),
    FinderCase(
        name="a_relationship_field_is_skipped",
        rack=FieldState(value=1, tracking_pool=allocated("pool-racks")),
        slot=FieldState(value=21),
        fields=("site",),
        holders={},
        expected=None,
        expected_reads=(),
    ),
    FinderCase(
        name="a_number_the_holding_object_holds_without_a_pool",
        rack=FieldState(value=1, tracking_pool=allocated("pool-racks")),
        slot=FieldState(value=21),
        fields=("rack",),
        holders={"slot-a": NumberHolder(label="1, 21", tracking_pool_ids={})},
        expected=PooledNumberConflict(
            numbers=(PooledNumber(field_name="rack", pool_name="racks", value=1, holding_pool_name=None),),
            node_id="slot-a",
            node_label="1, 21",
        ),
        expected_reads=(HolderRead(node_id="slot-a", attribute_names=("rack",)),),
    ),
    FinderCase(
        name="a_number_the_holding_object_holds_through_the_same_pool_names_no_other_pool",
        rack=FieldState(value=1, tracking_pool=allocated("pool-racks")),
        slot=FieldState(value=21),
        fields=("rack",),
        holders={"slot-a": NumberHolder(label="1, 21", tracking_pool_ids={"rack": "pool-racks"})},
        expected=PooledNumberConflict(
            numbers=(PooledNumber(field_name="rack", pool_name="racks", value=1, holding_pool_name=None),),
            node_id="slot-a",
            node_label="1, 21",
        ),
        expected_reads=(HolderRead(node_id="slot-a", attribute_names=("rack",)),),
    ),
    FinderCase(
        name="a_number_another_pool_tracks_names_that_pool",
        rack=FieldState(value=1, tracking_pool=allocated("pool-racks")),
        slot=FieldState(value=21),
        fields=("rack",),
        holders={"slot-a": NumberHolder(label="1, 21", tracking_pool_ids={"rack": "pool-legacy-racks"})},
        expected=PooledNumberConflict(
            numbers=(PooledNumber(field_name="rack", pool_name="racks", value=1, holding_pool_name="legacy-racks"),),
            node_id="slot-a",
            node_label="1, 21",
        ),
        expected_reads=(HolderRead(node_id="slot-a", attribute_names=("rack",)),),
    ),
    FinderCase(
        name="a_holding_object_that_cannot_be_read_is_named_by_its_id",
        rack=FieldState(value=1, tracking_pool=allocated("pool-racks")),
        slot=FieldState(value=21),
        fields=("rack",),
        holders={},
        expected=PooledNumberConflict(
            numbers=(PooledNumber(field_name="rack", pool_name="racks", value=1, holding_pool_name=None),),
            node_id="slot-a",
            node_label=None,
        ),
        expected_reads=(HolderRead(node_id="slot-a", attribute_names=("rack",)),),
    ),
    FinderCase(
        name="a_pool_without_a_name_is_named_by_its_id",
        rack=FieldState(value=1, tracking_pool=allocated("pool-unnamed")),
        slot=FieldState(value=21),
        fields=("rack",),
        holders={"slot-a": NumberHolder(label="1, 21", tracking_pool_ids={})},
        expected=PooledNumberConflict(
            numbers=(PooledNumber(field_name="rack", pool_name="pool-unnamed", value=1, holding_pool_name=None),),
            node_id="slot-a",
            node_label="1, 21",
        ),
        expected_reads=(HolderRead(node_id="slot-a", attribute_names=("rack",)),),
    ),
    FinderCase(
        name="numbers_of_two_pools_are_all_named_and_read_once",
        rack=FieldState(value=1, tracking_pool=allocated("pool-racks")),
        slot=FieldState(value=21, tracking_pool=allocated("pool-slots")),
        fields=("rack", "slot"),
        holders={"slot-a": NumberHolder(label="1, 21", tracking_pool_ids={"slot": "pool-slots"})},
        expected=PooledNumberConflict(
            numbers=(
                PooledNumber(field_name="rack", pool_name="racks", value=1, holding_pool_name=None),
                PooledNumber(field_name="slot", pool_name="slots", value=21, holding_pool_name=None),
            ),
            node_id="slot-a",
            node_label="1, 21",
        ),
        expected_reads=(HolderRead(node_id="slot-a", attribute_names=("rack", "slot")),),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in FINDER_CASES])
async def test_the_finder_names_the_numbers_pools_allocated_and_the_object_holding_them(case: FinderCase) -> None:
    holders = InMemoryHolders(holders=case.holders)
    finder = NumberPoolConflictFinder(pool_name_reader=InMemoryPoolNames(names=POOL_NAMES), holder_reader=holders)

    conflict = await finder.find(
        node=slot_node(rack=case.rack, slot=case.slot), fields=case.fields, holding_node_ids={"slot-a"}, branch=BRANCH
    )

    assert conflict == case.expected
    assert tuple(holders.reads) == case.expected_reads


async def test_the_finder_names_the_same_holding_object_whichever_order_the_ids_come_in() -> None:
    holders = InMemoryHolders(holders={})
    finder = NumberPoolConflictFinder(pool_name_reader=InMemoryPoolNames(names=POOL_NAMES), holder_reader=holders)
    node = slot_node(rack=FieldState(value=1, tracking_pool=allocated("pool-racks")), slot=FieldState(value=21))

    conflict = await finder.find(node=node, fields=("rack",), holding_node_ids=["slot-c", "slot-b"], branch=BRANCH)

    assert conflict is not None
    assert conflict.node_id == "slot-b"
    assert holders.reads == [HolderRead(node_id="slot-b", attribute_names=("rack",))]


@dataclass(frozen=True)
class AdviceCase:
    name: str
    conflict: PooledNumberConflict
    advice: str


def model_number(holding_pool_name: str | None = None) -> PooledNumber:
    return PooledNumber(field_name="model", pool_name="models", value=5, holding_pool_name=holding_pool_name)


def year_number(holding_pool_name: str | None = None) -> PooledNumber:
    return PooledNumber(field_name="year", pool_name="years", value=2020, holding_pool_name=holding_pool_name)


ADVICE_CASES = [
    AdviceCase(
        name="holding_object_without_a_label",
        conflict=PooledNumberConflict(numbers=(model_number(),), node_id="car-1", node_label=None),
        advice=(
            ": the 'models' pool allocated 5, which object 'car-1' already holds. Attach that number to the pool by "
            "updating object 'car-1' with value 5 and from_pool 'models', or change its number, then retry."
        ),
    ),
    AdviceCase(
        name="holding_object_with_a_label",
        conflict=PooledNumberConflict(numbers=(model_number(),), node_id="car-1", node_label="Accord"),
        advice=(
            ": the 'models' pool allocated 5, which object 'Accord' ('car-1') already holds. Attach that number to "
            "the pool by updating object 'car-1' with value 5 and from_pool 'models', or change its number, then "
            "retry."
        ),
    ),
    AdviceCase(
        name="number_tracked_by_another_pool",
        conflict=PooledNumberConflict(
            numbers=(model_number(holding_pool_name="legacy-models"),), node_id="car-1", node_label="Accord"
        ),
        advice=(
            ": the 'models' pool allocated 5, which object 'Accord' ('car-1') already holds through the "
            "'legacy-models' pool, because the ranges of the two pools overlap. Attach the numbers in the overlap to "
            "one of the pools, for example by updating object 'car-1' with value 5 and from_pool 'models', then "
            "change the ranges of the other pool so they no longer overlap, then retry."
        ),
    ),
    AdviceCase(
        name="numbers_of_two_pools",
        conflict=PooledNumberConflict(numbers=(model_number(), year_number()), node_id="car-1", node_label="Accord"),
        advice=(
            ": the 'models' pool allocated 5 for model and the 'years' pool allocated 2020 for year, which object "
            "'Accord' ('car-1') already holds. Attach those numbers to their pools by updating object 'car-1' with "
            "model value 5 and from_pool 'models', and year value 2020 and from_pool 'years', or change them, then "
            "retry."
        ),
    ),
    AdviceCase(
        name="numbers_of_two_pools_one_tracked_by_another_pool",
        conflict=PooledNumberConflict(
            numbers=(model_number(), year_number(holding_pool_name="legacy-years")),
            node_id="car-1",
            node_label="Accord",
        ),
        advice=(
            ": the 'models' pool allocated 5 for model and the 'years' pool allocated 2020 for year (also tracked "
            "by the 'legacy-years' pool), which object 'Accord' ('car-1') already holds. Attach those numbers to "
            "their pools by updating object 'car-1' with model value 5 and from_pool 'models', and year value 2020 "
            "and from_pool 'years', or change them; where another pool also tracks a number, the ranges of the two "
            "pools overlap, so also change the ranges of the other pool so they no longer overlap, then retry."
        ),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in ADVICE_CASES])
def test_the_advice_names_the_pool_the_holding_object_and_how_to_resolve_the_conflict(case: AdviceCase) -> None:
    assert case.conflict.advice() == case.advice
