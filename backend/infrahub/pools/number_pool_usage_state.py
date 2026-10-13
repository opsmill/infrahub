"""A number pool with its scope and ranges, as the dedicated number-pool queries read it on one branch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.pools.number_pool_space import to_pool_ranges
from infrahub.pools.number_ranges import EffectiveSpace
from infrahub.pools.scope import AllocationScope, Division, division_element_path

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreNumberPoolRange
    from infrahub.core.schema import AttributeSchema, RelationshipSchema
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.number_pool_repository import NumberPoolRepository
    from infrahub.pools.number_pool_space import SchemaAttributeDomains
    from infrahub.pools.number_ranges import NumberDomain
    from infrahub.pools.scope import AllocationScopeResolver, DivisionElementPath, ScopeElement


@dataclass(frozen=True)
class PoolScopeFields:
    """A pool's allocation scope, each element paired with the attribute or relationship holding it on the pool's kind."""

    pool_id: str
    element_fields: tuple[tuple[ScopeElement, AttributeSchema | RelationshipSchema], ...]
    """The scope elements in scope order; empty for an unscoped pool."""

    @property
    def elements(self) -> tuple[ScopeElement, ...]:
        return tuple(element for element, _ in self.element_fields)

    @property
    def is_empty(self) -> bool:
        return not self.element_fields

    @property
    def element_paths(self) -> list[DivisionElementPath]:
        return [division_element_path(field=field) for _, field in self.element_fields]

    def division_filter(self, entries: Sequence[tuple[str, object]] | None) -> Division | None:
        """Return the division the entries name, leaving out the elements no entry names, or None without entries.

        Raises:
            ValidationError: When entries are given on an unscoped pool, name no scope element or one twice, or give a
                value that does not have the type its element stores.

        """
        if not entries:
            return None
        if self.is_empty:
            raise ValidationError(
                f"The pool {self.pool_id} has no allocation scope; the division filter cannot be applied"
            )
        return Division.from_entries(entries=entries, element_fields=self.element_fields)

    def complete_division(self, entries: Sequence[tuple[str, object]] | None) -> Division | None:
        """Return the division the entries name, which on a scoped pool gives a value for every element.

        Raises:
            ValidationError: When the entries are refused as a division filter, or name a division that leaves out a
                scope element of a scoped pool.

        """
        division = self.division_filter(entries=entries)
        if not self.is_empty and (division is None or len(division.values) != len(self.element_fields)):
            raise ValidationError(
                f"The pool {self.pool_id} has an allocation scope; give a division with a value for every element "
                "to read its utilization"
            )
        return division


@dataclass(frozen=True)
class NumberPoolState:
    """A number pool with its scope resolved on the request branch and the ranges it allocates from."""

    pool: CoreNumberPool
    scope: PoolScopeFields
    ranges: tuple[CoreNumberPoolRange, ...]
    range_labels: dict[str, str]
    """The display label of each range, by range id."""
    domain: NumberDomain
    space: EffectiveSpace

    def range_space(self, range_id: str) -> EffectiveSpace:
        """Return the part of the pool's effective space that one of its ranges contributes.

        Raises:
            ValidationError: When `range_id` is not a range of the pool.

        """
        selected = [item for item in self.ranges if item.get_id() == range_id]
        if not selected:
            raise ValidationError(f"The range {range_id} does not belong to the pool {self.pool.get_id()}")
        return EffectiveSpace(ranges=to_pool_ranges(ranges=selected), domain=self.domain)


class NumberPoolStateLoader:
    """Reads a number pool, its ranges and the fields holding its scope elements, on the schema of `branch`."""

    def __init__(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        repository: NumberPoolRepository,
        scope_resolver: AllocationScopeResolver,
        domains: SchemaAttributeDomains,
    ) -> None:
        self.db = db
        self.branch = branch
        self.repository = repository
        self.scope_resolver = scope_resolver
        self.domains = domains

    async def load(self, pool_id: str) -> NumberPoolState:
        """Return the pool's state on the branch.

        Raises:
            NodeNotFoundError: When `pool_id` is not a number pool.
            ValidationError: When the schema of the branch does not define a scope element on the pool's kind.

        """
        pool = await NodeManager.get_one(
            db=self.db, id=pool_id, kind=InfrahubKind.NUMBERPOOL, branch=self.branch, raise_on_error=True
        )
        if not isinstance(pool, CoreNumberPool):
            raise NodeNotFoundError(node_type=InfrahubKind.NUMBERPOOL, identifier=pool_id, branch_name=self.branch.name)
        kind = str(pool.get_attribute("node").value)
        scope = AllocationScope.from_stored(value=pool.get_attribute("allocation_scope").value, pool=pool_id)
        element_fields = self.scope_resolver.element_fields(kind=kind, scope=scope, pool=pool_id)
        ranges = await self.repository.get_ranges(pool_id=pool_id)
        domain = self.domains.domain_of(kind=kind, attribute_name=str(pool.get_attribute("node_attribute").value))
        return NumberPoolState(
            pool=pool,
            scope=PoolScopeFields(pool_id=pool_id, element_fields=tuple(element_fields)),
            ranges=tuple(ranges),
            range_labels={item.get_id(): await item.get_display_label(db=self.db) for item in ranges},
            domain=domain,
            space=EffectiveSpace(ranges=to_pool_ranges(ranges=ranges), domain=domain),
        )
