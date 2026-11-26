from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.core.constants import InfrahubKind, PathType
from infrahub.core.validators.pool.scope_dependency import (
    ChangedField,
    DependentPoolFinder,
    PoolDependency,
    ScopeBreakage,
    ScopeViolationBuilder,
)
from infrahub.pools.scope import AllocationScope, ScopeElement
from infrahub.pools.scoped_number_pool_reader import ScopedNumberPool

DEVICE = "ScopeDevice"
SITE = ScopeElement(id="site-id", name="site")
ROLE = ScopeElement(id="role-id", name="role")


def _pool(pool_id: str, elements: tuple[ScopeElement, ...], tracked_attribute: str = "vlan_id") -> ScopedNumberPool:
    return ScopedNumberPool(
        id=pool_id,
        name=pool_id,
        kind=DEVICE,
        tracked_attribute=tracked_attribute,
        scope=AllocationScope(elements=elements),
    )


BY_SITE = _pool(pool_id="by-site", elements=(SITE,))
BY_ROLE = _pool(pool_id="by-role", elements=(ROLE,))
TRACKING_VLAN = _pool(pool_id="tracking-vlan", elements=(SITE,), tracked_attribute="vlan")


@dataclass(frozen=True)
class FinderCase:
    name: str
    field: ChangedField
    dependency: PoolDependency
    pools: list[ScopedNumberPool]
    expected: list[str]


FINDER_CASES = [
    FinderCase(
        name="scope-element-matched-by-id",
        field=ChangedField(kind=DEVICE, name="location", elements=(SITE,)),
        dependency=PoolDependency.SCOPE_ELEMENT,
        pools=[BY_SITE, BY_ROLE],
        expected=["by-site"],
    ),
    FinderCase(
        name="tracked-attribute-under-its-new-name",
        field=ChangedField(kind=DEVICE, name="vlan", elements=()),
        dependency=PoolDependency.TRACKED_ATTRIBUTE,
        pools=[BY_SITE, TRACKING_VLAN],
        expected=["tracking-vlan"],
    ),
    FinderCase(
        name="tracked-attribute-under-its-name-before-a-rename",
        field=ChangedField(kind=DEVICE, name="vlan_number", elements=(ScopeElement(id="vlan-id", name="vlan_id"),)),
        dependency=PoolDependency.TRACKED_ATTRIBUTE,
        pools=[BY_SITE, TRACKING_VLAN],
        expected=["by-site"],
    ),
]


@pytest.mark.parametrize("case", FINDER_CASES, ids=[case.name for case in FINDER_CASES])
def test_finds_the_pools_that_depend_on_the_changed_field(case: FinderCase) -> None:
    found = DependentPoolFinder().find(pools=case.pools, field=case.field, dependency=case.dependency)

    assert [pool.id for pool in found] == case.expected


@dataclass(frozen=True)
class BuilderCase:
    name: str
    breakage: ScopeBreakage
    pools: list[ScopedNumberPool]
    expected: list[tuple[str, str]]


BUILDER_CASES = [
    BuilderCase(
        name="scope-element",
        breakage=ScopeBreakage(dependency=PoolDependency.SCOPE_ELEMENT, reason="a scope element must stay required"),
        pools=[BY_SITE],
        expected=[
            ("by-site", "pool by-site divides its numbers by ScopeDevice.site; a scope element must stay required")
        ],
    ),
    BuilderCase(
        name="tracked-attribute",
        breakage=ScopeBreakage(
            dependency=PoolDependency.TRACKED_ATTRIBUTE,
            reason="a globally unique number cannot be allocated per division",
        ),
        pools=[BY_SITE],
        expected=[
            (
                "by-site",
                "pool by-site allocates ScopeDevice.site per division;"
                " a globally unique number cannot be allocated per division",
            )
        ],
    ),
]


@pytest.mark.parametrize("case", BUILDER_CASES, ids=[case.name for case in BUILDER_CASES])
def test_reports_one_violation_per_dependent_pool(case: BuilderCase) -> None:
    grouped_data_paths = ScopeViolationBuilder().build(
        branch_name="feature",
        field=ChangedField(kind=DEVICE, name="site", elements=(SITE,)),
        breakage=case.breakage,
        pools=case.pools,
    )

    data_paths = grouped_data_paths.get_all_data_paths()
    assert [(path.node_id, path.value) for path in data_paths] == case.expected
    assert {(path.branch, path.path_type, path.kind, path.field_name) for path in data_paths} == {
        ("feature", PathType.NODE, InfrahubKind.NUMBERPOOL, "site")
    }
