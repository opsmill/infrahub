from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, NumberPoolType
from infrahub.core.manager import NodeManager
from infrahub.core.node.lock_utils import NUMBER_POOL_TARGET_LOCK_NAMESPACE
from infrahub.core.query.resource_manager import NumberPoolGetHeldOutsideRanges
from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_overlap import NumberPoolOverlapChecker
from infrahub.pools.number_pool_range_validation import (
    NumberRangeBounds,
    validate_ranges_within_attribute,
)
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_pool_shorthand import NumberPoolShorthandMirror
from infrahub.pools.number_pool_space import attribute_domain
from infrahub.pools.number_pool_usage_nodes import HoldingObjectReader
from infrahub.pools.range_refusal import ranges_leave_held_numbers_refusal

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreNumberPoolRange
    from infrahub.core.schema import AttributeSchema
    from infrahub.core.schema.attribute_parameters import NumberPoolRangeParameters
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.number_ranges import NumberDomain


SCHEMA_POOL_EDIT_HINT = "update the schema in the default branch instead"
SCHEMA_POOL_SHORTHAND_REFUSED = (
    f"start_range or end_range can't be updated on schema defined pools, {SCHEMA_POOL_EDIT_HINT}"
)
SCHEMA_POOL_RANGES_REFUSED = f"ranges can't be updated on schema defined pools, {SCHEMA_POOL_EDIT_HINT}"
SCOPE_UPDATE_REFUSED = "allocation_scope can't be changed after the pool is created"
HELD_OUTSIDE_RANGES_LISTED = 20


def refuse_schema_pool(pool: Node, message: str) -> None:
    if pool.get_attribute("pool_type").get_value() == NumberPoolType.SCHEMA.value:
        raise ValidationError(input_value=message)


def pool_target_attribute(db: InfrahubDatabase, pool: Node, branch: Branch) -> AttributeSchema:
    """Return the schema of the attribute the pool allocates numbers for.

    Raises:
        ValidationError: When the pool does not name a model and an attribute.

    """
    kind = pool.get_attribute("node").value
    attribute_name = pool.get_attribute("node_attribute").value
    if not isinstance(kind, str) or not isinstance(attribute_name, str):
        raise ValidationError(input_value="The number pool does not name the attribute it allocates numbers for")
    return db.schema.get(name=kind, branch=branch, duplicate=False).get_attribute(name=attribute_name)


def refuse_ranges_outside_attribute(
    attribute: AttributeSchema, ranges: Iterable[NumberPoolRangeParameters | NumberRangeBounds]
) -> None:
    """Refuse ranges reaching outside the attribute's min_value / max_value or the numbers the database stores.

    Raises:
        ValidationError: Listing every range reaching outside the attribute's bounds, lowest range first.

    """
    validate_ranges_within_attribute(
        ranges=[NumberRangeBounds(start=item.start, end=item.end, weight=item.weight) for item in ranges],
        domain=attribute_domain(attribute),
    )


async def refuse_ranges_leaving_held_numbers(
    db: InfrahubDatabase, pool: Node, ranges: Sequence[NumberRangeBounds], domain: NumberDomain
) -> None:
    """Refuse pool ranges leaving a number the pool tracks, on any live branch, outside every range.

    A number already outside the ranges before the change is listed too, so the ranges are corrected to cover it.
    The message reads an open bound through `domain`, the numbers the pool's attribute accepts.

    Raises:
        ValidationError: Listing the lowest numbers outside `ranges`, each with its holder and branches.

    """
    query = await NumberPoolGetHeldOutsideRanges.init(
        db=db,
        pool_id=pool.get_id(),
        attribute_name=str(pool.get_attribute("node_attribute").value),
        node_kind=str(pool.get_attribute("node").value),
        ranges=[[pool_range.lower, pool_range.upper] for pool_range in ranges],
        listed=HELD_OUTSIDE_RANGES_LISTED,
    )
    await query.execute(db=db)
    total, held = query.get_data()
    if not total:
        return
    kind = str(pool.get_attribute("node").value)
    holders = await HoldingObjectReader(db=db).read(
        rows=[
            _HolderOnBranch(id=held_number.node_id, branch=_holding_branch(branches=held_number.branches))
            for held_number in held
            if held_number.node_id is not None
        ],
        kind=kind,
    )
    raise ValidationError(
        input_value=ranges_leave_held_numbers_refusal(
            pool_name=str(pool.get_attribute("name").value),
            ranges=[_ShownRange(*domain.resolve(start=pool_range.start, end=pool_range.end)) for pool_range in ranges],
            held=held,
            holders={
                held_number.attribute_id: holders[_holding_branch(branches=held_number.branches), held_number.node_id]
                for held_number in held
                if held_number.node_id is not None
            },
            total=total,
        )
    )


@dataclass(frozen=True)
class _ShownRange:
    start: int
    end: int


@dataclass(frozen=True)
class _HolderOnBranch:
    id: str
    branch: str


def _holding_branch(branches: Sequence[str]) -> str:
    """Return the branch to read a holder on: the default branch when it holds the number, else the first by name."""
    return registry.default_branch if registry.default_branch in branches else min(branches)


def pool_target_lock(kind: str, attribute_name: str) -> lock.InfrahubLock:
    """Return the lock serializing range writes of every pool allocating numbers for the kind's attribute.

    Taken before the lock of a pool, never after.
    """
    return lock.registry.get(name=f"{kind}.{attribute_name}", namespace=NUMBER_POOL_TARGET_LOCK_NAMESPACE)


async def refuse_ranges_overlapping_other_pools(
    db: InfrahubDatabase, pool: Node, attribute: AttributeSchema, ranges: Sequence[NumberRangeBounds]
) -> None:
    """Refuse pool ranges overlapping a range of another pool allocating numbers for the same unique attribute.

    A pool serves every branch, so the attribute counts as unique when it is unique on the request's branch or on the
    default branch.

    Raises:
        ValidationError: Naming every other pool's range that one of `ranges` overlaps.

    """
    kind = str(pool.get_attribute("node").value)
    await NumberPoolOverlapChecker(pool_reader=NumberPoolRepository(db=db)).check(
        pool_id=pool.get_id(),
        pool_name=str(pool.get_attribute("name").value),
        kind=kind,
        attribute=_unique_on_default_branch_or(attribute=attribute, kind=kind),
        ranges=ranges,
    )


def _unique_on_default_branch_or(attribute: AttributeSchema, kind: str) -> AttributeSchema:
    """Return the default branch's schema of the attribute when only that branch makes it unique, else `attribute`."""
    if attribute.unique:
        return attribute
    default_schema_branch = registry.schema.get_schema_branch(name=registry.default_branch)
    if not default_schema_branch.has(name=kind):
        return attribute
    default_attribute = default_schema_branch.get(name=kind, duplicate=False).get_attribute_or_none(name=attribute.name)
    return default_attribute if default_attribute is not None and default_attribute.unique else attribute


def range_bounds(ranges: Sequence[CoreNumberPoolRange]) -> list[NumberRangeBounds]:
    return [
        NumberRangeBounds(
            start=pool_range.start.value,
            end=pool_range.end.value,
            id=pool_range.get_id(),
            weight=pool_range.allocation_weight.value,
        )
        for pool_range in ranges
    ]


async def sync_shorthand(
    db: InfrahubDatabase, pool_id: str, ranges: Sequence[CoreNumberPoolRange], user_id: str
) -> Node:
    """Mirror the ranges into the pool's shorthand and return the pool as stored afterwards."""
    # Loaded here so the mirror's no-op check compares against the stored shorthand.
    pool = await NodeManager.get_one(db=db, id=pool_id, kind=InfrahubKind.NUMBERPOOL, raise_on_error=True)
    await NumberPoolShorthandMirror(repository=NumberPoolRepository(db=db)).sync(
        pool=pool, ranges=ranges, user_id=user_id
    )
    return pool
