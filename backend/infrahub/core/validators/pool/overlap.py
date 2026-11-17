from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.pools.number_pool_overlap import pool_overlap_refusal

from ..interface import ConstraintCheckerInterface

if TYPE_CHECKING:
    from infrahub.core.path import GroupedDataPaths
    from infrahub.pools.number_pool_overlap import AttributePoolRangeReader

    from ..model import SchemaConstraintValidatorRequest
    from .scope_dependency import ScopeViolationBuilder

UNIQUE_CONSTRAINT = "attribute.unique.update"


class UniqueAttributePoolOverlapChecker(ConstraintCheckerInterface):
    """Refuses making an attribute unique while pools allocating numbers for it have overlapping ranges.

    A pool hands out the numbers its own records leave free, so on a unique attribute each of two overlapping pools
    would offer what the other already gave, and the uniqueness constraint would refuse every such save.
    """

    # Only a schema change can make an attribute unique.
    triggered_by_data_change = False

    def __init__(self, pool_reader: AttributePoolRangeReader, violation_builder: ScopeViolationBuilder) -> None:
        self.pool_reader = pool_reader
        self.violation_builder = violation_builder

    @property
    def name(self) -> str:
        return "number_pool.overlap"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == UNIQUE_CONSTRAINT

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        """Return one violation per pool whose ranges overlap another pool's on the attribute the change makes unique.

        Raises:
            ValueError: When the request names no field.

        """
        field_name = request.schema_path.field_name
        if not field_name:
            raise ValueError("field_name is not defined")
        kind = request.schema_path.schema_kind
        if not request.schema_branch.has(name=kind):
            return []
        attribute = request.schema_branch.get(name=kind, duplicate=False).get_attribute_or_none(name=field_name)
        if attribute is None or not attribute.unique:
            return []

        pools = await self.pool_reader.get_attribute_pool_ranges(kind=kind, attribute_name=field_name)
        refusals: list[tuple[str, str]] = []
        for pool in sorted(pools, key=lambda pool: pool.pool_name):
            refusal = pool_overlap_refusal(
                pool_id=pool.pool_id, pool_name=pool.pool_name, ranges=pool.ranges, pools=pools, attribute=attribute
            )
            if refusal is not None:
                refusals.append((pool.pool_id, refusal))
        if not refusals:
            return []
        return [
            self.violation_builder.build_refusals(
                branch_name=request.branch.name, field_name=field_name, refusals=refusals
            )
        ]
