from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core.constants import InfrahubKind, NumberPoolType
from infrahub.core.manager import NodeManager
from infrahub.core.node.lock_utils import RESOURCE_POOL_LOCK_NAMESPACE
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters, NumberPoolRangeParameters
from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_range_validation import NumberRangeBounds, validate_ranges_within_attribute
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_pool_shorthand import NumberPoolShorthandMirror

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreNumberPoolRange
    from infrahub.core.schema import AttributeSchema
    from infrahub.database import InfrahubDatabase


SCHEMA_POOL_EDIT_HINT = "update the schema in the default branch instead"
SCHEMA_POOL_SHORTHAND_REFUSED = (
    f"start_range or end_range can't be updated on schema defined pools, {SCHEMA_POOL_EDIT_HINT}"
)
SCHEMA_POOL_RANGES_REFUSED = f"ranges can't be updated on schema defined pools, {SCHEMA_POOL_EDIT_HINT}"


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


def refuse_ranges_outside_attribute(attribute: AttributeSchema, ranges: Iterable[NumberPoolRangeParameters]) -> None:
    """Refuse ranges reaching outside the attribute's min_value / max_value.

    Raises:
        ValidationError: For the lowest range reaching outside the attribute's bounds.

    """
    if isinstance(attribute.parameters, NumberAttributeParameters):
        validate_ranges_within_attribute(
            ranges=[NumberRangeBounds(start=item.start, end=item.end) for item in ranges],
            min_value=attribute.parameters.min_value,
            max_value=attribute.parameters.max_value,
        )


def pool_lock(pool_id: str) -> lock.InfrahubLock:
    return lock.registry.get(name=pool_id, namespace=RESOURCE_POOL_LOCK_NAMESPACE)


def range_bounds(ranges: Sequence[CoreNumberPoolRange]) -> list[NumberRangeBounds]:
    return [
        NumberRangeBounds(start=int(pool_range.start.value), end=int(pool_range.end.value), id=pool_range.get_id())
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
