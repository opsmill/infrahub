from __future__ import annotations

import copy
import datetime
import re
from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.exceptions import ValidationError
from infrahub.pools.scope import AllocationScope, Division, ScopeElement

SITE = ScopeElement(id="17d0a4c2-0000-4000-8000-000000000001", name="site")
ROLE = ScopeElement(id="3b1f90ee-0000-4000-8000-000000000002", name="role")


@dataclass(frozen=True)
class RefusedEntryCase:
    name: str
    entry: Any
    shown: str


@dataclass(frozen=True)
class DivisionValuesCase:
    name: str
    values: tuple[Any, ...]


@dataclass(frozen=True)
class DistinctDivisionsCase:
    name: str
    first: tuple[Any, ...]
    second: tuple[Any, ...]


REFUSED_ENTRY_CASES = [
    RefusedEntryCase(name="plain-name", entry="site", shown='"site"'),
    RefusedEntryCase(name="missing-name", entry={"id": SITE.id}, shown=f'{{"id": "{SITE.id}"}}'),
    RefusedEntryCase(name="missing-id", entry={"name": "site"}, shown='{"name": "site"}'),
    RefusedEntryCase(name="id-not-text", entry={"id": 7, "name": "site"}, shown='{"id": 7, "name": "site"}'),
    RefusedEntryCase(name="name-not-text", entry={"id": SITE.id, "name": 3}, shown=f'{{"id": "{SITE.id}", "name": 3}}'),
    RefusedEntryCase(name="not-serializable", entry=datetime.date(2020, 1, 1), shown='"datetime.date(2020, 1, 1)"'),
]

DIVISION_VALUES_CASES = [
    DivisionValuesCase(name="scalar", values=("site-a-id",)),
    DivisionValuesCase(name="two-scalars", values=("site-a-id", "leaf")),
    DivisionValuesCase(name="list", values=(["red", "blue"],)),
    DivisionValuesCase(name="json", values=({"pod": 1, "row": "b"},)),
    DivisionValuesCase(name="no-value", values=("",)),
]

DISTINCT_DIVISIONS_CASES = [
    DistinctDivisionsCase(name="scalar", first=("site-a-id",), second=("site-b-id",)),
    DistinctDivisionsCase(name="order", first=("site-a-id", "leaf"), second=("leaf", "site-a-id")),
    DistinctDivisionsCase(name="list-order", first=(["red", "blue"],), second=(["blue", "red"],)),
    DistinctDivisionsCase(name="list-against-scalar", first=(["red"],), second=("red",)),
    DistinctDivisionsCase(name="json-value-type", first=({"pod": 1},), second=({"pod": "1"},)),
    DistinctDivisionsCase(name="no-value-against-value", first=("",), second=("site-a-id",)),
    DistinctDivisionsCase(name="integer-against-boolean", first=(1,), second=(True,)),
    DistinctDivisionsCase(name="integer-against-float", first=({"pod": 1},), second=({"pod": 1.0},)),
]


class TestAllocationScopeStoredForm:
    @pytest.mark.parametrize("stored", [None, []], ids=["absent", "empty"])
    def test_absent_or_empty_value_reads_as_unscoped(self, stored: list[Any] | None) -> None:
        scope = AllocationScope.from_stored(value=stored, pool="vlan-per-site")

        assert scope.is_empty
        assert scope.element_names == ()
        assert scope.to_stored() == []

    def test_stored_elements_read_back_in_order(self) -> None:
        stored = [{"id": ROLE.id, "name": "role"}, {"id": SITE.id, "name": "site"}]

        scope = AllocationScope.from_stored(value=stored, pool="vlan-per-site")

        assert scope.elements == (ROLE, SITE)
        assert not scope.is_empty
        assert scope.element_names == ("role", "site")
        assert scope.to_stored() == stored

    def test_scope_round_trips_through_its_stored_form(self) -> None:
        scope = AllocationScope(elements=(SITE, ROLE))

        assert AllocationScope.from_stored(value=scope.to_stored(), pool="vlan-per-site") == scope

    @pytest.mark.parametrize("case", REFUSED_ENTRY_CASES, ids=[case.name for case in REFUSED_ENTRY_CASES])
    def test_entry_that_is_not_an_element_is_refused_naming_the_pool(self, case: RefusedEntryCase) -> None:
        expected = (
            f"allocation_scope of pool vlan-per-site: the stored entry {case.shown} is not an element "
            'with an "id" and a "name"; recreate the pool to set its scope'
        )

        with pytest.raises(ValidationError, match=f"^{re.escape(expected)}$"):
            AllocationScope.from_stored(value=[{"id": ROLE.id, "name": "role"}, case.entry], pool="vlan-per-site")

    def test_stored_value_that_is_not_a_list_is_refused_naming_the_pool(self) -> None:
        expected = (
            'allocation_scope of pool vlan-per-site: the stored value "site" is not a list of elements; '
            "recreate the pool to set its scope"
        )

        with pytest.raises(ValidationError, match=f"^{re.escape(expected)}$"):
            AllocationScope.from_stored(value="site", pool="vlan-per-site")


class TestDivisionKey:
    @pytest.mark.parametrize("case", DIVISION_VALUES_CASES, ids=[case.name for case in DIVISION_VALUES_CASES])
    def test_equal_divisions_share_a_key(self, case: DivisionValuesCase) -> None:
        first = Division(values=case.values)
        second = Division(values=copy.deepcopy(case.values))

        assert first == second
        assert first.key == second.key
        assert {first, second} == {first}

    def test_key_does_not_depend_on_the_key_order_of_a_document(self) -> None:
        assert Division(values=({"pod": 1, "row": "b"},)).key == Division(values=({"row": "b", "pod": 1},)).key

    def test_key_is_the_same_in_every_process(self) -> None:
        division = Division(values=("site-a-id", ["red", "blue"], {"pod": 1}))

        assert division.key == "8236f44c632d78e56d3959c98a974fe6f324044beb26ccb062b3a18a081fb7ed"

    @pytest.mark.parametrize("case", DISTINCT_DIVISIONS_CASES, ids=[case.name for case in DISTINCT_DIVISIONS_CASES])
    def test_different_divisions_have_different_keys(self, case: DistinctDivisionsCase) -> None:
        assert Division(values=case.first) != Division(values=case.second)
        assert Division(values=case.first).key != Division(values=case.second).key
