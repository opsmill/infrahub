from __future__ import annotations

import re
from dataclasses import dataclass

import pytest

from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_usage_state import PoolScopeFields
from infrahub.pools.scope import Division, DivisionElementPath, ScopeElement
from tests.helpers.number_pool import SCOPED_DEVICE

SITE = ScopeElement(id="site-field-id", name="site")
ROLE = ScopeElement(id="role-field-id", name="role")
SITE_FIELD = SCOPED_DEVICE.get_relationship(name="site")
ROLE_FIELD = SCOPED_DEVICE.get_attribute(name="role")
SITE_PATH = DivisionElementPath(name=SITE_FIELD.get_identifier(), relationship_direction=SITE_FIELD.direction)
ROLE_PATH = DivisionElementPath(name="role")

SCOPED = PoolScopeFields(pool_id="vlan-per-site-role", element_fields=((SITE, SITE_FIELD), (ROLE, ROLE_FIELD)))
UNSCOPED = PoolScopeFields(pool_id="vlans", element_fields=())

INCOMPLETE_DIVISION = (
    "The pool vlan-per-site-role has an allocation scope; give a division with a value for every element to read "
    "its utilization"
)
DIVISION_ON_UNSCOPED_POOL = "The pool vlans has no allocation scope; the division filter cannot be applied"


@dataclass(frozen=True)
class DivisionCase:
    name: str
    scope: PoolScopeFields
    entries: list[tuple[str, object]] | None
    expected: Division | None


@dataclass(frozen=True)
class RefusedDivisionCase:
    name: str
    scope: PoolScopeFields
    entries: list[tuple[str, object]] | None
    message: str


DIVISION_FILTER_CASES = [
    DivisionCase(name="no-entries-on-a-scoped-pool", scope=SCOPED, entries=None, expected=None),
    DivisionCase(name="empty-entries-on-a-scoped-pool", scope=SCOPED, entries=[], expected=None),
    DivisionCase(name="no-entries-on-an-unscoped-pool", scope=UNSCOPED, entries=None, expected=None),
    DivisionCase(
        name="one-element-of-two",
        scope=SCOPED,
        entries=[("role", "leaf")],
        expected=Division(elements=(ROLE_PATH,), values=("leaf",)),
    ),
    DivisionCase(
        name="entries-out-of-scope-order",
        scope=SCOPED,
        entries=[("role", "leaf"), ("site", "site-a-id")],
        expected=Division(elements=(SITE_PATH, ROLE_PATH), values=("site-a-id", "leaf")),
    ),
]

COMPLETE_DIVISION_CASES = [
    DivisionCase(name="no-entries-on-an-unscoped-pool", scope=UNSCOPED, entries=None, expected=None),
    DivisionCase(
        name="every-element",
        scope=SCOPED,
        entries=[("site", "site-a-id"), ("role", "leaf")],
        expected=Division(elements=(SITE_PATH, ROLE_PATH), values=("site-a-id", "leaf")),
    ),
]

REFUSED_COMPLETE_DIVISION_CASES = [
    RefusedDivisionCase(name="no-entries", scope=SCOPED, entries=None, message=INCOMPLETE_DIVISION),
    RefusedDivisionCase(name="empty-entries", scope=SCOPED, entries=[], message=INCOMPLETE_DIVISION),
    RefusedDivisionCase(
        name="one-element-of-two", scope=SCOPED, entries=[("role", "leaf")], message=INCOMPLETE_DIVISION
    ),
    RefusedDivisionCase(
        name="entries-on-an-unscoped-pool", scope=UNSCOPED, entries=[("site", "x")], message=DIVISION_ON_UNSCOPED_POOL
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(case, id=case.name) for case in DIVISION_FILTER_CASES])
def test_division_filter_names_the_elements_the_entries_give(test_case: DivisionCase) -> None:
    assert test_case.scope.division_filter(entries=test_case.entries) == test_case.expected


def test_division_filter_is_refused_on_an_unscoped_pool() -> None:
    with pytest.raises(ValidationError, match=f"^{re.escape(DIVISION_ON_UNSCOPED_POOL)}$"):
        UNSCOPED.division_filter(entries=[("site", "site-a-id")])


@pytest.mark.parametrize("test_case", [pytest.param(case, id=case.name) for case in COMPLETE_DIVISION_CASES])
def test_complete_division_gives_a_value_for_every_element(test_case: DivisionCase) -> None:
    assert test_case.scope.complete_division(entries=test_case.entries) == test_case.expected


@pytest.mark.parametrize("test_case", [pytest.param(case, id=case.name) for case in REFUSED_COMPLETE_DIVISION_CASES])
def test_complete_division_refuses_a_division_leaving_out_an_element(test_case: RefusedDivisionCase) -> None:
    with pytest.raises(ValidationError, match=f"^{re.escape(test_case.message)}$"):
        test_case.scope.complete_division(entries=test_case.entries)


def test_the_elements_and_their_paths_follow_scope_order() -> None:
    assert SCOPED.elements == (SITE, ROLE)
    assert SCOPED.element_paths == [SITE_PATH, ROLE_PATH]
