"""Schema changes the scope checker accepts, reading no pool when the field keeps its properties."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.core.constants import SchemaPathType
from tests.unit.core.validators.number_pool_scope.helpers import (
    ALL_POOLS,
    DEVICE,
    HOLDER,
    POD_HOLDER,
    RecordingPoolSource,
    SchemaChangeCase,
    StaticSchemaSource,
    build_checker,
    build_request,
    build_schema_branch,
    device_role_kind,
    device_site_removed,
    device_tags_removed,
    pod_removed,
    saved_schema,
    unchanged,
)

ACCEPTED_CASES = [
    SchemaChangeCase(
        name="relationship-staying-required",
        constraint_name="relationship.optional.update",
        kind=DEVICE,
        field_name="site",
        path_type=SchemaPathType.RELATIONSHIP,
        change=unchanged,
        expected_kinds_read=[],
    ),
    SchemaChangeCase(
        name="attribute-staying-not-unique",
        constraint_name="attribute.unique.update",
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=unchanged,
        expected_kinds_read=[],
    ),
    SchemaChangeCase(
        name="attribute-made-another-scalar-kind",
        constraint_name="attribute.kind.update",
        kind=DEVICE,
        field_name="role",
        path_type=SchemaPathType.ATTRIBUTE,
        change=device_role_kind("Number"),
        expected_kinds_read=[],
    ),
    SchemaChangeCase(
        name="attribute-outside-any-scope-removed",
        constraint_name="node.attribute.remove",
        kind=DEVICE,
        field_name="tags",
        path_type=SchemaPathType.ATTRIBUTE,
        change=device_tags_removed,
        expected_kinds_read=[{DEVICE}],
    ),
    SchemaChangeCase(
        name="kind-without-scoped-pool",
        constraint_name="node.relationship.remove",
        kind=DEVICE,
        field_name="site",
        path_type=SchemaPathType.RELATIONSHIP,
        change=device_site_removed,
        expected_kinds_read=[{DEVICE}],
        pools=(),
    ),
    SchemaChangeCase(
        name="element-of-implementing-kind-removed",
        constraint_name="node.attribute.remove",
        kind=POD_HOLDER,
        field_name="pod",
        path_type=SchemaPathType.ATTRIBUTE,
        change=pod_removed,
        expected_kinds_read=[{POD_HOLDER, HOLDER}],
    ),
]


@dataclass(frozen=True)
class UnchangedFieldCase:
    name: str
    constraint_name: str
    field_name: str
    path_type: SchemaPathType


UNCHANGED_FIELD_CASES = [
    UnchangedFieldCase(
        name="optional-attribute",
        constraint_name="attribute.optional.update",
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
    ),
    UnchangedFieldCase(
        name="optional-relationship",
        constraint_name="relationship.optional.update",
        field_name="rack",
        path_type=SchemaPathType.RELATIONSHIP,
    ),
    UnchangedFieldCase(
        name="relationship-of-cardinality-many",
        constraint_name="relationship.cardinality.update",
        field_name="links",
        path_type=SchemaPathType.RELATIONSHIP,
    ),
    UnchangedFieldCase(
        name="attribute-holding-a-list",
        constraint_name="attribute.kind.update",
        field_name="tags",
        path_type=SchemaPathType.ATTRIBUTE,
    ),
    UnchangedFieldCase(
        name="unique-attribute",
        constraint_name="attribute.unique.update",
        field_name="name",
        path_type=SchemaPathType.ATTRIBUTE,
    ),
]


class TestAcceptedChanges:
    @pytest.mark.parametrize("case", ACCEPTED_CASES, ids=[case.name for case in ACCEPTED_CASES])
    async def test_accepts_a_change_no_pool_depends_on(self, case: SchemaChangeCase) -> None:
        candidate_schema = saved_schema()
        case.change(candidate_schema)
        pool_source = RecordingPoolSource(pools=case.pools)
        checker = build_checker(
            pool_source=pool_source,
            schema_source=StaticSchemaSource(schema_branch=build_schema_branch(saved_schema())),
        )

        grouped_data_paths = await checker.check(
            build_request(case=case, candidate=build_schema_branch(candidate_schema))
        )

        assert [path for grouped in grouped_data_paths for path in grouped.get_all_data_paths()] == []
        assert pool_source.requested_kinds == case.expected_kinds_read

    @pytest.mark.parametrize("case", UNCHANGED_FIELD_CASES, ids=[case.name for case in UNCHANGED_FIELD_CASES])
    async def test_reports_no_violation_without_reading_pools(self, case: UnchangedFieldCase) -> None:
        """A proposed change or a merge also requests these constraints when only the data of a field changed."""
        pool_source = RecordingPoolSource(pools=ALL_POOLS)
        checker = build_checker(
            pool_source=pool_source,
            schema_source=StaticSchemaSource(schema_branch=build_schema_branch(saved_schema())),
        )
        request = build_request(
            case=SchemaChangeCase(
                name=case.name,
                constraint_name=case.constraint_name,
                kind=DEVICE,
                field_name=case.field_name,
                path_type=case.path_type,
                change=unchanged,
                expected_kinds_read=[],
            ),
            candidate=build_schema_branch(saved_schema()),
        )

        assert await checker.check(request) == []
        assert pool_source.requested_kinds == []
