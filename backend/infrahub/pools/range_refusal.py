from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.pools.number_ranges import EffectiveSpace, NumberDomain

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.pools.number_ranges import PoolRange


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
        f"The {pool_name} pool cannot track {value} on '{attribute_name}', because {value} is outside its ranges: "
        f"{_describe_ranges(ranges)}. Send a number inside those ranges."
    )


def tracked_edit_refusal(pool_name: str, attribute_name: str, ranges: Sequence[PoolRange], value: int) -> str:
    """Return why the attribute the pool tracks cannot hold `value`, which is outside its ranges."""
    return (
        f"'{attribute_name}' is tracked by the {pool_name} pool, so it cannot hold {value}, which is outside the "
        f"pool's ranges: {_describe_ranges(ranges)}. To set {value} and stop the pool tracking '{attribute_name}', "
        f"send 'value: {value}' together with 'from_pool: null'."
    )


def tracked_empty_refusal(pool_name: str, attribute_name: str) -> str:
    """Return why the attribute the pool tracks cannot be emptied."""
    return (
        f"'{attribute_name}' is tracked by the {pool_name} pool, so it cannot be emptied. To empty '{attribute_name}' "
        "and stop the pool tracking it, send 'value: null' together with 'from_pool: null'."
    )


def tracked_reset_refusal(pool_name: str, attribute_name: str) -> str:
    """Return why the attribute the pool tracks cannot be reset to its default."""
    return (
        f"'{attribute_name}' is tracked by the {pool_name} pool, so it cannot be reset to its default. To reset "
        f"'{attribute_name}' and stop the pool tracking it, send 'is_default: true' together with 'from_pool: null'."
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
    held = ", ".join(f"branch '{branch_value.branch}' holds {branch_value.value}" for branch_value in outside)
    return (
        f"The {pool_name} pool cannot track '{attribute_name}', because a pool tracks an attribute on every branch "
        f"and {held} outside its ranges: {_describe_ranges(ranges)}. "
        "Change the number on that branch, or delete the branch, before attaching."
    )


def _describe_ranges(ranges: Sequence[PoolRange]) -> str:
    if not ranges:
        return "no ranges"
    ordered = sorted(ranges, key=lambda pool_range: (pool_range.start, pool_range.end))
    return ", ".join(f"{pool_range.start}-{pool_range.end}" for pool_range in ordered)
