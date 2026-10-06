from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.exceptions import SchemaNotFoundError
from infrahub.log import get_logger
from infrahub.pools.number_ranges import NumberDomain, NumberSpan, PoolRange

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreNumberPoolRange
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.attribute_schema import AttributeSchema

log = get_logger()


def to_pool_ranges(ranges: Sequence[CoreNumberPoolRange]) -> list[PoolRange]:
    """Map a pool's range nodes to the ranges its allocation space is built from."""
    return [
        PoolRange(
            start=int(pool_range.start.value),
            end=int(pool_range.end.value),
            weight=pool_range.allocation_weight.value or 0,
            id=pool_range.get_id(),
        )
        for pool_range in ranges
    ]


def attribute_domain(attribute: AttributeSchema | None) -> NumberDomain:
    """Return the numbers `attribute` accepts, unbounded when it declares no number parameters."""
    if attribute is None or not isinstance(attribute.parameters, NumberAttributeParameters):
        return NumberDomain()
    parameters = attribute.parameters
    singles = [NumberSpan(start=value, end=value) for value in parameters.get_excluded_single_values()]
    ranges = [NumberSpan(start=start, end=end) for start, end in parameters.get_excluded_ranges()]
    return NumberDomain(lower=parameters.min_value, upper=parameters.max_value, exclusions=tuple(singles + ranges))


class NodeSchemaSource(Protocol):
    """Resolves a kind to its schema on a branch, raising SchemaNotFoundError for an unknown kind."""

    def get(self, name: str, branch: Branch | str | None = None, duplicate: bool = True) -> MainSchemaTypes: ...


class SchemaAttributeDomains:
    """Looks up, in the schema of one branch, the numbers the attribute a pool feeds accepts."""

    def __init__(self, schema: NodeSchemaSource, branch: Branch) -> None:
        self._schema = schema
        self._branch = branch

    def domain_of(self, kind: str, attribute_name: str) -> NumberDomain:
        """Return the numbers `attribute_name` of `kind` accepts.

        A pool can outlive the kind or attribute it was created for, and then has no domain to clip its ranges to.
        """
        try:
            node_schema = self._schema.get(name=kind, branch=self._branch, duplicate=False)
        except SchemaNotFoundError:
            log.warning(
                "Number pool feeds a kind the schema does not hold, so its ranges are not clipped",
                kind=kind,
                attribute=attribute_name,
                branch=self._branch.name,
            )
            return NumberDomain()
        attribute = node_schema.get_attribute_or_none(name=attribute_name)
        if attribute is None:
            log.warning(
                "Number pool feeds an attribute its kind does not hold, so its ranges are not clipped",
                kind=kind,
                attribute=attribute_name,
                branch=self._branch.name,
            )
        return attribute_domain(attribute=attribute)
