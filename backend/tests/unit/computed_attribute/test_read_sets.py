from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute.read_sets import derived_reads_are_scopable
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.helpers.schema.car import CAR
from tests.helpers.schema.person import PERSON

if TYPE_CHECKING:
    from infrahub.core.schema import NodeSchema


def _branch_with_car(car: NodeSchema) -> SchemaBranch:
    branch = SchemaBranch(cache={}, name="test")
    branch.set(name=CAR.kind, schema=car)
    branch.set(name=PERSON.kind, schema=PERSON)
    return branch


def _car_with(**overrides: object) -> NodeSchema:
    car = deepcopy(CAR)
    for name, value in overrides.items():
        setattr(car, name, value)
    return car


@dataclass(frozen=True, kw_only=True)
class Case:
    name: str
    car: NodeSchema
    derived_reads: frozenset[str]
    expected: bool


CASES = [
    Case(
        name="an_own_attribute_derived_read_is_scopable",
        car=CAR,
        derived_reads=frozenset({"display_label"}),
        expected=True,
    ),
    Case(
        name="a_relationship_crossing_derived_read_is_not_scopable",
        car=_car_with(display_label="owner__name__value"),
        derived_reads=frozenset({"display_label"}),
        expected=False,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_derived_reads_are_scopable(case: Case) -> None:
    result = derived_reads_are_scopable(
        schema_branch=_branch_with_car(case.car), kind=CAR.kind, derived_reads=case.derived_reads
    )
    assert result is case.expected


def test_derived_reads_are_scopable_is_false_for_a_kind_absent_from_the_branch() -> None:
    branch = SchemaBranch(cache={}, name="test")

    result = derived_reads_are_scopable(schema_branch=branch, kind=CAR.kind, derived_reads=frozenset({"display_label"}))

    assert result is False
