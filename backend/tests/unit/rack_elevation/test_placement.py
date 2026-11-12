from __future__ import annotations

import pytest

from infrahub.rack_elevation.models import RackFace, RackItemPlacement
from infrahub.rack_elevation.placement import check_placement, order_items

from .helpers import build_item, build_rack


def test_item_without_position_and_face_is_accepted() -> None:
    candidate = build_item("spare1")

    assert check_placement(rack=build_rack(), others=[], candidate=candidate) is None


@pytest.mark.parametrize("position", [1, 12])
def test_one_unit_item_is_accepted_at_the_bottom_and_top_unit(position: int) -> None:
    candidate = build_item("leaf1", position=position, face=RackFace.FRONT)

    assert check_placement(rack=build_rack(), others=[], candidate=candidate) is None


def test_two_unit_item_is_accepted_when_it_ends_on_the_top_unit() -> None:
    candidate = build_item("srv1", position=11, face=RackFace.FRONT, u_height=2)

    assert check_placement(rack=build_rack(), others=[], candidate=candidate) is None


@pytest.mark.parametrize(("position", "u_height"), [(12, 2), (0, 1), (-1, 1), (13, 1)])
def test_item_that_does_not_fit_in_the_rack_is_refused(position: int, u_height: int) -> None:
    candidate = build_item("srv1", position=position, face=RackFace.FRONT, u_height=u_height)

    violation = check_placement(rack=build_rack(), others=[], candidate=candidate)

    assert violation is not None
    assert violation.constraint == "RACK_POSITION_OUT_OF_RANGE"
    assert violation.field == "position"
    assert "R1 (12U)" in violation.detail


def test_out_of_range_detail_names_the_units_of_a_two_unit_item() -> None:
    candidate = build_item("srv1", position=12, face=RackFace.FRONT, u_height=2)

    violation = check_placement(rack=build_rack(), others=[], candidate=candidate)

    assert violation is not None
    assert violation.detail == "Units 12-13 do not fit in rack R1 (12U)"


def test_half_depth_items_on_opposite_faces_can_share_a_unit() -> None:
    front = build_item("blank1", position=10, face=RackFace.FRONT)
    rear = build_item("pp1", position=10, face=RackFace.REAR)

    assert check_placement(rack=build_rack(), others=[front], candidate=rear) is None


def test_half_depth_items_on_the_same_face_cannot_share_a_unit() -> None:
    blank = build_item("blank1", position=10, face=RackFace.FRONT)
    patch_panel = build_item("pp1", position=10, face=RackFace.FRONT)

    violation = check_placement(rack=build_rack(), others=[blank], candidate=patch_panel)

    assert violation is not None
    assert violation.constraint == "RACK_UNITS_OCCUPIED"
    assert violation.detail == "Unit 10 front is used by blank1"


def test_full_depth_item_blocks_the_other_face() -> None:
    leaf1 = build_item("leaf1", position=12, face=RackFace.FRONT, full_depth=True)
    leaf2 = build_item("leaf2", position=12, face=RackFace.REAR, full_depth=True)

    violation = check_placement(rack=build_rack(), others=[leaf1], candidate=leaf2)

    assert violation is not None
    assert violation.constraint == "RACK_UNITS_OCCUPIED"
    assert violation.detail == "Unit 12 rear is used by leaf1"


def test_half_depth_item_cannot_use_a_unit_of_a_full_depth_item_on_the_other_face() -> None:
    leaf1 = build_item("leaf1", position=12, face=RackFace.FRONT, full_depth=True)
    panel = build_item("pp1", position=12, face=RackFace.REAR)

    violation = check_placement(rack=build_rack(), others=[leaf1], candidate=panel)

    assert violation is not None
    assert violation.constraint == "RACK_UNITS_OCCUPIED"


def test_two_unit_item_overlapping_the_top_of_another_item_is_refused() -> None:
    leaf = build_item("leaf1", position=2, face=RackFace.FRONT, full_depth=True)
    server = build_item("srv1", position=1, face=RackFace.FRONT, u_height=2, full_depth=True)

    violation = check_placement(rack=build_rack(), others=[leaf], candidate=server)

    assert violation is not None
    assert violation.detail == "Unit 2 front is used by leaf1"


def test_adjacent_items_do_not_overlap() -> None:
    leaf = build_item("leaf1", position=3, face=RackFace.FRONT, full_depth=True)
    server = build_item("srv1", position=1, face=RackFace.FRONT, u_height=2, full_depth=True)

    assert check_placement(rack=build_rack(), others=[leaf], candidate=server) is None


def test_unpositioned_items_do_not_occupy_units() -> None:
    spare = build_item("spare1")
    candidate = build_item("leaf1", position=1, face=RackFace.FRONT)

    assert check_placement(rack=build_rack(), others=[spare], candidate=candidate) is None


def test_zero_u_item_with_a_position_is_refused() -> None:
    pdu = build_item("pdu1", position=5, face=RackFace.FRONT, u_height=0)

    violation = check_placement(rack=build_rack(), others=[], candidate=pdu)

    assert violation is not None
    assert violation.constraint == "RACK_ZERO_U_HAS_NO_POSITION"
    assert violation.detail == "pdu1 is a 0U item and cannot use a unit"


def test_item_without_a_type_cannot_take_a_position() -> None:
    spare = build_item("spare2", position=1, face=RackFace.FRONT, typed=False)

    violation = check_placement(rack=build_rack(), others=[], candidate=spare)

    assert violation is not None
    assert violation.constraint == "RACK_TYPE_REQUIRED"
    assert violation.detail == "spare2 has no type, so its height is not known"


@pytest.mark.parametrize(
    ("position", "face", "field"),
    [(5, None, "face"), (None, RackFace.FRONT, "position")],
)
def test_position_and_face_must_be_set_together(position: int | None, face: RackFace | None, field: str) -> None:
    candidate = build_item("leaf2", position=position, face=face)

    violation = check_placement(rack=build_rack(), others=[], candidate=candidate)

    assert violation is not None
    assert violation.constraint == "RACK_FACE_REQUIRED"
    assert violation.field == field


def test_missing_face_is_reported_before_the_zero_u_rule() -> None:
    pdu = build_item("pdu1", position=5, face=None, u_height=0)

    violation = check_placement(rack=build_rack(), others=[], candidate=pdu)

    assert violation is not None
    assert violation.constraint == "RACK_FACE_REQUIRED"


def test_zero_u_rule_is_reported_before_the_range_rule() -> None:
    pdu = build_item("pdu1", position=99, face=RackFace.FRONT, u_height=0)

    violation = check_placement(rack=build_rack(), others=[], candidate=pdu)

    assert violation is not None
    assert violation.constraint == "RACK_ZERO_U_HAS_NO_POSITION"


def test_range_rule_is_reported_before_the_occupied_rule() -> None:
    leaf = build_item("leaf1", position=12, face=RackFace.FRONT, full_depth=True)
    server = build_item("srv1", position=12, face=RackFace.FRONT, u_height=2, full_depth=True)

    violation = check_placement(rack=build_rack(), others=[leaf], candidate=server)

    assert violation is not None
    assert violation.constraint == "RACK_POSITION_OUT_OF_RANGE"


def test_placement_is_derived_from_position_and_height() -> None:
    assert build_item("a", position=3, face=RackFace.FRONT).placement == RackItemPlacement.MOUNTED
    assert build_item("b").placement == RackItemPlacement.UNPOSITIONED
    assert build_item("c", u_height=0).placement == RackItemPlacement.ZERO_U
    assert build_item("d", typed=False).placement == RackItemPlacement.UNPOSITIONED


def test_items_are_ordered_by_position_descending_then_unpositioned_then_zero_u() -> None:
    items = [
        build_item("pdu1", u_height=0),
        build_item("spare1"),
        build_item("srv1", position=1, face=RackFace.FRONT, u_height=2),
        build_item("pp1", position=10, face=RackFace.REAR),
        build_item("blank1", position=10, face=RackFace.FRONT),
        build_item("leaf1", position=12, face=RackFace.FRONT),
    ]

    assert [item.display_label for item in order_items(items)] == [
        "leaf1",
        "blank1",
        "pp1",
        "srv1",
        "spare1",
        "pdu1",
    ]
