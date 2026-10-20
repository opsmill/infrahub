from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind, PathType
from infrahub.core.path import DataPath, GroupedDataPaths

if TYPE_CHECKING:
    from infrahub.pools.scope import ScopeElement
    from infrahub.pools.scoped_number_pool_reader import ScopedNumberPool


class PoolDependency(StrEnum):
    """What ties a pool to the changed field."""

    SCOPE_ELEMENT = "scope_element"
    TRACKED_ATTRIBUTE = "tracked_attribute"


@dataclass(frozen=True)
class ScopeBreakage:
    """A schema change that stops the pools depending on the changed field from dividing their space."""

    dependency: PoolDependency
    reason: str


@dataclass(frozen=True)
class ChangedField:
    """A field a schema change touches, under its name in the change and as the scope elements it was before it."""

    kind: str
    name: str
    elements: tuple[ScopeElement, ...]

    @property
    def names(self) -> set[str]:
        """The names the field carries in the change and before it."""
        return {self.name} | {element.name for element in self.elements}


class DependentPoolFinder:
    """Picks, among the scoped pools that share a kind's fields, the pools that depend on a changed field."""

    def find(
        self, pools: list[ScopedNumberPool], field: ChangedField, dependency: PoolDependency
    ) -> list[ScopedNumberPool]:
        """Return the pools that depend on the changed field.

        A pool depends on it through a scope element matched by its id, or through its tracked attribute matched
        by one of the field's names.
        """
        if dependency == PoolDependency.SCOPE_ELEMENT:
            element_ids = {element.id for element in field.elements}
            return [pool for pool in pools if element_ids & {stored.id for stored in pool.scope.elements}]
        # A pool stores its tracked attribute by name, which is the pre-change name when the same load renames it.
        return [pool for pool in pools if pool.tracked_attribute in field.names]


class ScopeViolationBuilder:
    """Turns the pools a schema change breaks into one violation per pool, naming the pool and the field."""

    def build(
        self,
        branch_name: str,
        field: ChangedField,
        breakage: ScopeBreakage,
        pools: list[ScopedNumberPool],
    ) -> GroupedDataPaths:
        """Return one violation per pool, set on the pool and the changed field, that says what the change breaks."""
        return self.build_refusals(
            branch_name=branch_name,
            field_name=field.name,
            refusals=[(pool.id, self._describe(pool=pool, field=field, breakage=breakage)) for pool in pools],
        )

    @staticmethod
    def build_refusals(branch_name: str, field_name: str, refusals: list[tuple[str, str]]) -> GroupedDataPaths:
        """Return one violation per pool id, set on the pool and the changed field, carrying the refusal given."""
        grouped_data_paths = GroupedDataPaths()
        for pool_id, refusal in refusals:
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=branch_name,
                    path_type=PathType.NODE,
                    node_id=pool_id,
                    kind=InfrahubKind.NUMBERPOOL,
                    field_name=field_name,
                    value=refusal,
                )
            )
        return grouped_data_paths

    @staticmethod
    def _describe(pool: ScopedNumberPool, field: ChangedField, breakage: ScopeBreakage) -> str:
        """Say how the pool depends on the field and why the change breaks that dependency."""
        if breakage.dependency == PoolDependency.TRACKED_ATTRIBUTE:
            return f"pool {pool.name} allocates {field.kind}.{field.name} per division; {breakage.reason}"
        return f"pool {pool.name} divides its numbers by {field.kind}.{field.name}; {breakage.reason}"
