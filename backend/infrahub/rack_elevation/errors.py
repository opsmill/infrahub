from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

from infrahub.errors.exceptions import AttributeConstraintViolationError

if TYPE_CHECKING:
    from infrahub.rack_elevation.models import RackPlacementViolation


def raise_placement_violation(violation: RackPlacementViolation, node_kind: str, field_name: str) -> NoReturn:
    raise AttributeConstraintViolationError(
        node_kind=node_kind,
        field_name=field_name,
        constraint=violation.constraint,
        detail=violation.detail,
        message=violation.detail,
    )
