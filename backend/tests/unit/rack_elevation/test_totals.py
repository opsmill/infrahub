from __future__ import annotations

from infrahub.rack_elevation.models import RackFace
from infrahub.rack_elevation.placement import compute_totals

from .helpers import build_item, build_rack


def test_items_on_both_faces_of_one_unit_count_the_unit_once() -> None:
    items = [
        build_item("blank1", position=10, face=RackFace.FRONT),
        build_item("pp1", position=10, face=RackFace.REAR),
    ]

    totals = compute_totals(rack=build_rack(), items=items)

    assert totals.used_units == 1


def test_full_depth_item_counts_its_units_once() -> None:
    items = [build_item("srv1", position=1, face=RackFace.FRONT, u_height=2, full_depth=True)]

    totals = compute_totals(rack=build_rack(), items=items)

    assert totals.used_units == 2


def test_utilization_rounds_down() -> None:
    items = [
        build_item("srv1", position=1, face=RackFace.FRONT, u_height=2),
        build_item("pp1", position=10, face=RackFace.REAR),
        build_item("leaf2", position=11, face=RackFace.FRONT),
        build_item("leaf1", position=12, face=RackFace.FRONT),
    ]

    totals = compute_totals(rack=build_rack(u_height=12), items=items)

    assert totals.used_units == 5
    assert totals.utilization == 41


def test_total_weight_includes_unpositioned_and_zero_u_items() -> None:
    items = [
        build_item("leaf1", position=12, face=RackFace.FRONT, weight=8),
        build_item("pdu1", u_height=0, weight=5),
        build_item("spare1", weight=8),
        build_item("srv1", position=1, face=RackFace.FRONT, u_height=2, weight=25),
        build_item("untyped", typed=False),
    ]

    totals = compute_totals(rack=build_rack(), items=items)

    assert totals.total_weight == 46


def test_total_weight_is_none_when_no_item_has_a_weight() -> None:
    items = [build_item("leaf1", position=12, face=RackFace.FRONT), build_item("spare1")]

    totals = compute_totals(rack=build_rack(), items=items)

    assert totals.total_weight is None


def test_empty_rack_has_no_used_units() -> None:
    totals = compute_totals(rack=build_rack(), items=[])

    assert (totals.used_units, totals.utilization, totals.total_weight) == (0, 0, None)
