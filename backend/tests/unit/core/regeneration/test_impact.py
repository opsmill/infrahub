from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from infrahub.core.regeneration.impact import reads_unscopable_derived_field
from tests.helpers.schema.car import CAR

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes, NodeSchema


def _car_with(**overrides: object) -> NodeSchema:
    car = deepcopy(CAR)
    for name, value in overrides.items():
        setattr(car, name, value)
    return car


@dataclass(frozen=True, kw_only=True)
class UnscopableCase:
    name: str
    readable_fields_by_kind: dict[str, set[str]]
    schemas: dict[str, MainSchemaTypes] = field(default_factory=dict)
    expected: bool


UNSCOPABLE_CASES = [
    UnscopableCase(
        name="no_derived_read_is_scopable",
        readable_fields_by_kind={"TestCar": {"name"}},
        expected=False,
    ),
    UnscopableCase(
        name="display_label_from_own_attribute_is_scopable",
        readable_fields_by_kind={"TestCar": {"display_label"}},
        schemas={"TestCar": CAR},
        expected=False,
    ),
    UnscopableCase(
        name="hfid_from_own_attribute_is_scopable",
        readable_fields_by_kind={"TestCar": {"human_friendly_id"}},
        schemas={"TestCar": _car_with(human_friendly_id=["name__value"])},
        expected=False,
    ),
    UnscopableCase(
        name="hfid_composed_from_a_peer_is_unscopable",
        readable_fields_by_kind={"TestCar": {"human_friendly_id"}},
        schemas={"TestCar": _car_with(human_friendly_id=["owner__name__value", "name__value"])},
        expected=True,
    ),
    UnscopableCase(
        name="display_label_crossing_a_relationship_is_unscopable",
        readable_fields_by_kind={"TestCar": {"display_label"}},
        schemas={"TestCar": _car_with(display_labels=["owner__name__value"])},
        expected=True,
    ),
    UnscopableCase(
        name="one_unscopable_read_among_scopable_ones_widens",
        readable_fields_by_kind={"TestCar": {"display_label"}, "TestOwner": {"human_friendly_id"}},
        schemas={
            "TestCar": CAR,
            "TestOwner": _car_with(human_friendly_id=["owner__name__value"]),
        },
        expected=True,
    ),
]


@pytest.mark.parametrize("case", UNSCOPABLE_CASES, ids=lambda case: case.name)
def test_reads_unscopable_derived_field(case: UnscopableCase) -> None:
    assert (
        reads_unscopable_derived_field(
            readable_fields_by_kind=case.readable_fields_by_kind,
            get_node_schema=lambda kind: case.schemas[kind],
        )
        is case.expected
    )
