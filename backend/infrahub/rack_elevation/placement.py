from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.rack_elevation.constants import FIRST_UNIT, PERCENT, RackConstraint, RackPlaceArgument
from infrahub.rack_elevation.models import (
    RackItemPlacement,
    RackItemSnapshot,
    RackPlacementViolation,
    RackSnapshot,
    RackTotals,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.rack_elevation.models import RackFace


def check_placement(
    rack: RackSnapshot, others: Iterable[RackItemSnapshot], candidate: RackItemSnapshot
) -> RackPlacementViolation | None:
    """Return the first rule the candidate breaks in the rack, or None when it can be saved.

    The candidate carries the position and face it is about to get. `others` must not contain the candidate itself.
    """
    return (
        _check_face(candidate=candidate)
        or _check_type(candidate=candidate)
        or _check_range(rack=rack, candidate=candidate)
        or _check_occupied(others=others, candidate=candidate)
    )


def _check_face(candidate: RackItemSnapshot) -> RackPlacementViolation | None:
    if (candidate.position is None) == (candidate.face is None):
        return None
    return RackPlacementViolation(
        constraint=RackConstraint.FACE_REQUIRED.value,
        field=RackPlaceArgument.FACE.value if candidate.position is not None else RackPlaceArgument.POSITION.value,
        detail="A mounted item needs a position and a face",
    )


def _check_type(candidate: RackItemSnapshot) -> RackPlacementViolation | None:
    if candidate.position is None:
        return None
    if candidate.is_zero_u:
        return RackPlacementViolation(
            constraint=RackConstraint.ZERO_U_HAS_NO_POSITION.value,
            field=RackPlaceArgument.POSITION.value,
            detail=f"{candidate.display_label} is a 0U item and cannot use a unit",
        )
    if candidate.type_id is None:
        return RackPlacementViolation(
            constraint=RackConstraint.TYPE_REQUIRED.value,
            field=RackPlaceArgument.POSITION.value,
            detail=f"{candidate.display_label} has no type, so its height is not known",
        )
    return None


def _check_range(rack: RackSnapshot, candidate: RackItemSnapshot) -> RackPlacementViolation | None:
    if candidate.position is None:
        return None
    first_unit = candidate.position
    last_unit = first_unit + candidate.u_height - 1
    if first_unit >= FIRST_UNIT and last_unit <= rack.u_height:
        return None
    return RackPlacementViolation(
        constraint=RackConstraint.POSITION_OUT_OF_RANGE.value,
        field=RackPlaceArgument.POSITION.value,
        detail=_out_of_range_detail(rack=rack, first_unit=first_unit, last_unit=last_unit),
    )


def _check_occupied(others: Iterable[RackItemSnapshot], candidate: RackItemSnapshot) -> RackPlacementViolation | None:
    if candidate.position is None or candidate.face is None:
        return None
    for other in others:
        if other.position is not None and _overlaps(candidate=candidate, candidate_face=candidate.face, other=other):
            return RackPlacementViolation(
                constraint=RackConstraint.UNITS_OCCUPIED.value,
                field=RackPlaceArgument.POSITION.value,
                detail=(
                    f"Unit {max(candidate.position, other.position)} {candidate.face.value} "
                    f"is used by {other.display_label}"
                ),
            )
    return None


def compute_totals(rack: RackSnapshot, items: Iterable[RackItemSnapshot]) -> RackTotals:
    used: set[int] = set()
    weights: list[int] = []
    for item in items:
        if item.weight is not None:
            weights.append(item.weight)
        if item.position is not None:
            used.update(range(item.position, item.position + item.u_height))
    used_units = len(used)
    return RackTotals(
        used_units=used_units,
        utilization=used_units * PERCENT // rack.u_height if rack.u_height else 0,
        total_weight=sum(weights) if weights else None,
    )


def _out_of_range_detail(rack: RackSnapshot, first_unit: int, last_unit: int) -> str:
    if first_unit == last_unit:
        return f"Unit {first_unit} does not exist in rack {rack.display_label} ({rack.u_height}U)"
    return f"Units {first_unit}-{last_unit} do not fit in rack {rack.display_label} ({rack.u_height}U)"


def _overlaps(candidate: RackItemSnapshot, candidate_face: RackFace, other: RackItemSnapshot) -> bool:
    if other.position is None or other.face is None or candidate.position is None:
        return False
    if not (candidate.full_depth or other.full_depth or other.face == candidate_face):
        return False
    candidate_last = candidate.position + candidate.u_height - 1
    other_last = other.position + other.u_height - 1
    return candidate.position <= other_last and other.position <= candidate_last


def order_items(items: Iterable[RackItemSnapshot]) -> list[RackItemSnapshot]:
    """Mounted items by position descending, then the unpositioned items, then the 0U items."""
    return sorted(items, key=_order_key)


def _order_key(item: RackItemSnapshot) -> tuple[int, int, str, str]:
    face = item.face.value if item.face is not None else ""
    match item.placement:
        case RackItemPlacement.MOUNTED:
            return (0, -(item.position or 0), face, item.display_label)
        case RackItemPlacement.UNPOSITIONED:
            return (1, 0, face, item.display_label)
        case RackItemPlacement.ZERO_U:
            return (2, 0, face, item.display_label)
