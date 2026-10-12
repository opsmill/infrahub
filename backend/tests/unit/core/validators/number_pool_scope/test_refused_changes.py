"""Schema changes the scope checker refuses, with one violation per pool they break."""

from __future__ import annotations

import pytest

from infrahub.core.constants import InfrahubKind, PathType, SchemaPathType
from infrahub.core.validators.pool.scope import NumberPoolScopeChecker
from tests.unit.core.validators.number_pool_scope.helpers import (
    BRANCH,
    DEVICE,
    DEVICE_POOL_BY_ROLE,
    DEVICE_POOL_BY_SITE,
    HOLDER,
    POD_HOLDER,
    RecordingPoolSource,
    SchemaChangeCase,
    StaticSchemaSource,
    build_request,
    build_schema_branch,
    device_role_kind,
    device_role_optional,
    device_role_removed,
    device_site_many,
    device_site_optional,
    device_site_removed,
    device_site_renamed_and_made_optional,
    device_vlan_id_renamed_and_made_unique,
    device_vlan_id_unique,
    holder_site_optional,
    saved_schema,
)

REFUSED_CASES = [
    SchemaChangeCase(
        name="relationship-made-optional",
        constraint_name="relationship.optional.update",
        kind=DEVICE,
        field_name="site",
        path_type=SchemaPathType.RELATIONSHIP,
        change=device_site_optional,
        expected=[
            (
                "vlan-per-site",
                "pool vlan-per-site divides its numbers by ScopeDevice.site; a scope element must stay required",
            )
        ],
        expected_kinds_read=[{DEVICE}],
    ),
    SchemaChangeCase(
        name="attribute-made-optional",
        constraint_name="attribute.optional.update",
        kind=DEVICE,
        field_name="role",
        path_type=SchemaPathType.ATTRIBUTE,
        change=device_role_optional,
        expected=[
            (
                "vlan-per-role",
                "pool vlan-per-role divides its numbers by ScopeDevice.role; a scope element must stay required",
            )
        ],
        expected_kinds_read=[{DEVICE}],
    ),
    SchemaChangeCase(
        name="relationship-renamed-and-made-optional",
        constraint_name="relationship.optional.update",
        kind=DEVICE,
        field_name="location",
        path_type=SchemaPathType.RELATIONSHIP,
        change=device_site_renamed_and_made_optional,
        expected=[
            (
                "vlan-per-site",
                "pool vlan-per-site divides its numbers by ScopeDevice.location; a scope element must stay required",
            )
        ],
        expected_kinds_read=[{DEVICE}],
    ),
    SchemaChangeCase(
        name="relationship-made-many",
        constraint_name="relationship.cardinality.update",
        kind=DEVICE,
        field_name="site",
        path_type=SchemaPathType.RELATIONSHIP,
        change=device_site_many,
        expected=[
            (
                "vlan-per-site",
                "pool vlan-per-site divides its numbers by ScopeDevice.site;"
                " a scope element must stay a relationship of cardinality one",
            )
        ],
        expected_kinds_read=[{DEVICE}],
    ),
    SchemaChangeCase(
        name="tracked-attribute-made-unique",
        constraint_name="attribute.unique.update",
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=device_vlan_id_unique,
        expected=[
            (
                "vlan-per-site",
                "pool vlan-per-site allocates ScopeDevice.vlan_id per division;"
                " a globally unique number cannot be allocated per division",
            ),
            (
                "vlan-per-role",
                "pool vlan-per-role allocates ScopeDevice.vlan_id per division;"
                " a globally unique number cannot be allocated per division",
            ),
        ],
        expected_kinds_read=[{DEVICE}],
        pools=(DEVICE_POOL_BY_SITE, DEVICE_POOL_BY_ROLE),
    ),
    SchemaChangeCase(
        name="tracked-attribute-renamed-and-made-unique",
        constraint_name="attribute.unique.update",
        kind=DEVICE,
        field_name="vlan",
        path_type=SchemaPathType.ATTRIBUTE,
        change=device_vlan_id_renamed_and_made_unique,
        expected=[
            (
                "vlan-per-site",
                "pool vlan-per-site allocates ScopeDevice.vlan per division;"
                " a globally unique number cannot be allocated per division",
            ),
            (
                "vlan-per-role",
                "pool vlan-per-role allocates ScopeDevice.vlan per division;"
                " a globally unique number cannot be allocated per division",
            ),
        ],
        expected_kinds_read=[{DEVICE}],
        pools=(DEVICE_POOL_BY_SITE, DEVICE_POOL_BY_ROLE),
    ),
    *[
        SchemaChangeCase(
            name=f"attribute-made-{kind.lower()}",
            constraint_name="attribute.kind.update",
            kind=DEVICE,
            field_name="role",
            path_type=SchemaPathType.ATTRIBUTE,
            change=device_role_kind(kind),
            expected=[
                (
                    "vlan-per-role",
                    "pool vlan-per-role divides its numbers by ScopeDevice.role;"
                    " a scope element must hold a single scalar value",
                )
            ],
            expected_kinds_read=[{DEVICE}],
        )
        for kind in ("List", "JSON", "Any")
    ],
    SchemaChangeCase(
        name="relationship-removed",
        constraint_name="node.relationship.remove",
        kind=DEVICE,
        field_name="site",
        path_type=SchemaPathType.RELATIONSHIP,
        change=device_site_removed,
        expected=[
            (
                "vlan-per-site",
                "pool vlan-per-site divides its numbers by ScopeDevice.site;"
                " a scope element cannot be removed while the pool exists",
            )
        ],
        expected_kinds_read=[{DEVICE}],
    ),
    SchemaChangeCase(
        name="attribute-removed",
        constraint_name="node.attribute.remove",
        kind=DEVICE,
        field_name="role",
        path_type=SchemaPathType.ATTRIBUTE,
        change=device_role_removed,
        expected=[
            (
                "vlan-per-role",
                "pool vlan-per-role divides its numbers by ScopeDevice.role;"
                " a scope element cannot be removed while the pool exists",
            )
        ],
        expected_kinds_read=[{DEVICE}],
    ),
    SchemaChangeCase(
        name="generic-element-made-optional",
        constraint_name="relationship.optional.update",
        kind=HOLDER,
        field_name="site",
        path_type=SchemaPathType.RELATIONSHIP,
        change=holder_site_optional,
        expected=[
            (
                "holder-per-site",
                "pool holder-per-site divides its numbers by ScopeHolder.site; a scope element must stay required",
            ),
            (
                "pod-holder-per-site",
                "pool pod-holder-per-site divides its numbers by ScopeHolder.site; a scope element must stay required",
            ),
        ],
        expected_kinds_read=[{HOLDER, POD_HOLDER}],
    ),
]


class TestRefusedChanges:
    @pytest.mark.parametrize("case", REFUSED_CASES, ids=[case.name for case in REFUSED_CASES])
    async def test_reports_one_violation_per_pool_the_change_breaks(self, case: SchemaChangeCase) -> None:
        candidate_schema = saved_schema()
        case.change(candidate_schema)
        pool_source = RecordingPoolSource(pools=case.pools)
        checker = NumberPoolScopeChecker(
            pool_source=pool_source,
            schema_source=StaticSchemaSource(schema_branch=build_schema_branch(saved_schema())),
        )

        grouped_data_paths = await checker.check(
            build_request(case=case, candidate=build_schema_branch(candidate_schema))
        )

        data_paths = [path for grouped in grouped_data_paths for path in grouped.get_all_data_paths()]
        assert [(path.node_id, path.value) for path in data_paths] == case.expected
        assert {(path.branch, path.path_type, path.kind, path.field_name) for path in data_paths} == {
            (BRANCH.name, PathType.NODE, InfrahubKind.NUMBERPOOL, case.field_name)
        }
        assert pool_source.requested_kinds == case.expected_kinds_read
