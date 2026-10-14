from __future__ import annotations

from infrahub.core.query.resource_manager import NumberPoolDivisionResult
from infrahub.core.schema import AttributeSchema
from infrahub.pools.number import UtilizationFigures
from infrahub.pools.number_pool_divisions_reader import build_division_usages, division_peer_ids
from infrahub.pools.number_pool_usage import DivisionEntry, PeerSummary
from infrahub.pools.number_pool_usage_state import PoolScopeFields
from infrahub.pools.scope import ScopeElement
from tests.helpers.number_pool import SCOPED_DEVICE, SCOPED_SITE

SITE = ScopeElement(id="site-field-id", name="site")
ROLE = ScopeElement(id="role-field-id", name="role")
ACTIVE = ScopeElement(id="active-field-id", name="active")
PRIORITY = ScopeElement(id="priority-field-id", name="priority")

SITE_ROLE = PoolScopeFields(
    pool_id="vlan-per-site-role",
    element_fields=(
        (SITE, SCOPED_DEVICE.get_relationship(name="site")),
        (ROLE, SCOPED_DEVICE.get_attribute(name="role")),
    ),
)
ACTIVE_PRIORITY = PoolScopeFields(
    pool_id="vlan-per-flags",
    element_fields=(
        (ACTIVE, AttributeSchema(name="active", kind="Boolean")),
        (PRIORITY, AttributeSchema(name="priority", kind="Number")),
    ),
)
PARIS = PeerSummary(display_label="Paris", kind=SCOPED_SITE.kind)
SIZE = 100


def _result(
    values: tuple[str | int | float | bool, ...], used: int = 1, used_default_branch: int = 1
) -> NumberPoolDivisionResult:
    return NumberPoolDivisionResult(values=values, used=used, used_default_branch=used_default_branch)


def test_a_relationship_entry_carries_its_peer_label_and_kind() -> None:
    (division,) = build_division_usages(
        scope=SITE_ROLE, results=[_result(values=("site-a-id", "leaf"))], size=SIZE, peers={"site-a-id": PARIS}
    )

    assert division.entries == (
        DivisionEntry(id=SITE.id, path="site", value="site-a-id", display_label="Paris", peer_kind=SCOPED_SITE.kind),
        DivisionEntry(id=ROLE.id, path="role", value="leaf", display_label="leaf", peer_kind=None),
    )
    assert division.display_label == "Paris / leaf"


def test_a_peer_that_cannot_be_read_is_labeled_with_its_id() -> None:
    (division,) = build_division_usages(
        scope=SITE_ROLE, results=[_result(values=("site-gone-id", "leaf"))], size=SIZE, peers={}
    )

    assert division.entries[0] == DivisionEntry(
        id=SITE.id, path="site", value="site-gone-id", display_label="site-gone-id", peer_kind=None
    )
    assert division.display_label == "site-gone-id / leaf"


def test_an_object_without_a_peer_holds_an_empty_entry() -> None:
    (division,) = build_division_usages(scope=SITE_ROLE, results=[_result(values=("", "leaf"))], size=SIZE, peers={})

    assert division.entries[0] == DivisionEntry(id=SITE.id, path="site", value="", display_label="", peer_kind=None)


def test_a_boolean_and_a_number_keep_their_type_and_read_as_text() -> None:
    (division,) = build_division_usages(
        scope=ACTIVE_PRIORITY, results=[_result(values=(True, 48))], size=SIZE, peers={}
    )

    assert division.entries == (
        DivisionEntry(id=ACTIVE.id, path="active", value=True, display_label="true", peer_kind=None),
        DivisionEntry(id=PRIORITY.id, path="priority", value=48, display_label="48", peer_kind=None),
    )
    assert division.display_label == "true / 48"


def test_the_figures_of_a_division_are_measured_over_the_whole_pool() -> None:
    (division,) = build_division_usages(
        scope=SITE_ROLE,
        results=[_result(values=("site-a-id", "leaf"), used=5, used_default_branch=3)],
        size=SIZE,
        peers={},
    )

    assert division.figures == UtilizationFigures(size=SIZE, used_default_branch=3, used_branches=2)


def test_divisions_are_ordered_by_utilization_descending_then_by_display_label() -> None:
    results = [
        _result(values=("", "spine"), used=1),
        _result(values=("", "leaf"), used=1),
        _result(values=("", "border"), used=4, used_default_branch=4),
    ]

    divisions = build_division_usages(scope=SITE_ROLE, results=results, size=SIZE, peers={})

    assert [division.display_label for division in divisions] == [" / border", " / leaf", " / spine"]


def test_the_peer_ids_are_the_relationship_values_that_name_a_peer() -> None:
    results = [
        _result(values=("site-a-id", "leaf")),
        _result(values=("", "spine")),
        _result(values=("site-b-id", "leaf")),
    ]

    assert division_peer_ids(scope=SITE_ROLE, results=results) == {"site-a-id", "site-b-id"}
