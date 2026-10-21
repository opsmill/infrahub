from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from infrahub.pools.number_ranges import EffectiveSpace, NumberDomain, format_bounds

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from infrahub.core.query.resource_manager import HeldNumber
    from infrahub.pools.number_pool_usage import HoldingObject
    from infrahub.pools.number_ranges import PoolRange


class Bounded(Protocol):
    @property
    def start(self) -> int: ...

    @property
    def end(self) -> int: ...


@dataclass(frozen=True, kw_only=True)
class BranchValue:
    """The number an attribute holds on one live branch."""

    attribute_id: str
    branch: str
    value: int


def is_within_ranges(ranges: Sequence[PoolRange], value: int) -> bool:
    """Return whether one of the pool's ranges holds `value`; a pool without ranges holds none."""
    return EffectiveSpace(ranges=ranges, domain=NumberDomain()).contains(value)


def untracked_attach_refusal(pool_name: str, attribute_name: str, ranges: Sequence[PoolRange], value: int) -> str:
    """Return why a pool that does not track the attribute cannot start tracking `value`, which is outside its ranges."""
    return (
        f"The '{pool_name}' pool cannot track {value} on '{attribute_name}', because {value} is outside its ranges: "
        f"{_describe_ranges(ranges)}. Choose a number inside those ranges."
    )


def tracked_edit_refusal(pool_name: str, attribute_name: str, ranges: Sequence[PoolRange], value: int) -> str:
    """Return why the attribute the pool tracks cannot hold `value`, which is outside its ranges."""
    return (
        f"'{attribute_name}' is tracked by the '{pool_name}' pool, so it cannot hold {value}, which is outside the "
        f"pool's ranges: {_describe_ranges(ranges)}. Choose a number inside those ranges, or remove the "
        f"'{pool_name}' pool from '{attribute_name}' in the same change that sets it to {value}."
    )


def tracked_empty_refusal(pool_name: str, attribute_name: str) -> str:
    """Return why the attribute the pool tracks cannot be emptied."""
    return (
        f"'{attribute_name}' is tracked by the '{pool_name}' pool, so it cannot be emptied. To empty "
        f"'{attribute_name}', remove the '{pool_name}' pool from it in the same change."
    )


def tracked_reset_refusal(pool_name: str, attribute_name: str) -> str:
    """Return why the attribute the pool tracks cannot be reset to its default."""
    return (
        f"'{attribute_name}' is tracked by the '{pool_name}' pool, so it cannot be reset to its default. To reset "
        f"'{attribute_name}', remove the '{pool_name}' pool from it in the same change."
    )


def other_branch_refusal(
    pool_name: str, attribute_name: str, ranges: Sequence[PoolRange], branch_values: Sequence[BranchValue]
) -> str | None:
    """Return why the pool cannot track an attribute some branch holds outside its ranges, or None when none does."""
    outside = sorted(
        (
            branch_value
            for branch_value in branch_values
            if not is_within_ranges(ranges=ranges, value=branch_value.value)
        ),
        key=lambda branch_value: (branch_value.branch, branch_value.value),
    )
    if not outside:
        return None
    refused = f"Cannot use the '{pool_name}' pool for '{attribute_name}'"
    pool_ranges = f"the pool's {'range' if len(ranges) == 1 else 'ranges'} ({_describe_ranges(ranges)})"
    if len(outside) == 1:
        branch_value = outside[0]
        message = (
            f"{refused}: the pool would also apply to branch '{branch_value.branch}', where this object has the value "
            f"{branch_value.value}, outside {pool_ranges}."
        )
        remedy = f"First change the value on '{branch_value.branch}' or delete that branch."
    else:
        held = ", ".join(f"'{branch_value.branch}' has {branch_value.value}" for branch_value in outside)
        message = (
            f"{refused}: the pool would also apply to other branches where this object has a value outside "
            f"{pool_ranges}: {held}."
        )
        remedy = "First change the value on those branches or delete them."
    if not ranges:
        return message
    return f"{message} {remedy}"


def ranges_leave_held_numbers_refusal(
    pool_name: str,
    ranges: Sequence[Bounded],
    held: Sequence[HeldNumber],
    holders: Mapping[str, HoldingObject],
    total: int,
) -> str:
    """Return why the pool cannot take `ranges`, listing the first numbers it tracks outside them out of `total`.

    `holders` gives, by attribute id, the object holding each number; a number without one is named by its attribute.
    """
    listed = "; ".join(
        _describe_held(held_number=held_number, holder=holders.get(held_number.attribute_id)) for held_number in held
    )
    if total > len(held):
        listed += f"; and {total - len(held)} more"
    return (
        f"Changing the ranges of the {pool_name} pool to {_describe_ranges(ranges)} would leave numbers it tracks "
        f"outside every range: {listed}. Keep a range covering each of these numbers, or change those numbers first."
    )


def _describe_held(held_number: HeldNumber, holder: HoldingObject | None) -> str:
    holder_name = (
        f"{holder.kind} '{holder.display_label}'" if holder is not None else f"attribute {held_number.attribute_id}"
    )
    branches = ", ".join(f"'{branch}'" for branch in sorted(held_number.branches))
    noun = "branch" if len(held_number.branches) == 1 else "branches"
    return f"{holder_name} holds {held_number.value} on {noun} {branches}"


def _describe_ranges(ranges: Sequence[Bounded]) -> str:
    if not ranges:
        return "no ranges"
    ordered = sorted(ranges, key=lambda pool_range: (pool_range.start, pool_range.end))
    return ", ".join(format_bounds(start=pool_range.start, end=pool_range.end) for pool_range in ordered)
