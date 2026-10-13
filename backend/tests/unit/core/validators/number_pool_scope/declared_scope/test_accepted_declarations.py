"""Schema changes that a declared allocation scope accepts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import SchemaPathType
from infrahub.core.path import SchemaPath
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from tests.helpers.number_pool import SCOPED_SITE
from tests.unit.core.validators.number_pool_scope.declared_scope.helpers import (
    DEVICE_SCHEMA_POOL_ID,
    HOLDER_SCHEMA_POOL,
    POD_HOLDER_SCHEMA_POOL,
    SCHEMA_POOLS,
    SCOPE_CONSTRAINT,
    declare_on_device,
    declared_checker,
    declared_request,
    declared_schema,
    device_site_renamed_and_declared,
    device_tags_renamed,
    unvalidated_schema_branch,
    without_device,
)
from tests.unit.core.validators.number_pool_scope.helpers import (
    BRANCH,
    DEVICE,
    RecordingPoolSource,
    unchanged,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.pools.scoped_number_pool_reader import ScopedNumberPool


@dataclass(frozen=True)
class AcceptedDeclarationCase:
    name: str
    constraint_name: str
    kind: str
    field_name: str
    path_type: SchemaPathType
    change: Callable[[SchemaRoot], None]
    expected_ids_read: list[set[str]]
    pools: tuple[ScopedNumberPool, ...] = field(default=SCHEMA_POOLS)


def device_declaration_change(name: str, scope: list[str]) -> AcceptedDeclarationCase:
    return AcceptedDeclarationCase(
        name=name,
        constraint_name=SCOPE_CONSTRAINT,
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=declare_on_device(scope),
        expected_ids_read=[{DEVICE_SCHEMA_POOL_ID}],
    )


MATCHING_DECLARATION_CASES = [
    device_declaration_change(name="declaration-unchanged", scope=["site", "role"]),
    # Reordering the declaration keeps the same divisions, so its ids match the stored scope.
    device_declaration_change(name="declaration-reordered", scope=["role", "site"]),
    # The declaration already names the renamed field, so its ids match the stored scope.
    AcceptedDeclarationCase(
        name="relationship-renamed-declaration-following-under-the-declaration",
        constraint_name=SCOPE_CONSTRAINT,
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=device_site_renamed_and_declared,
        expected_ids_read=[{DEVICE_SCHEMA_POOL_ID}],
    ),
    AcceptedDeclarationCase(
        name="attribute-outside-the-declaration-renamed",
        constraint_name="attribute.name.update",
        kind=DEVICE,
        field_name="labels",
        path_type=SchemaPathType.ATTRIBUTE,
        change=device_tags_renamed,
        expected_ids_read=[{DEVICE_SCHEMA_POOL_ID}],
    ),
]

# A pool id matching no pool leaves no stored scope, so the declaration is validated as a new one.
MISSING_POOL_CASES = [
    AcceptedDeclarationCase(
        name="declaration-whose-pool-is-not-found",
        constraint_name=SCOPE_CONSTRAINT,
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=declare_on_device(["site"]),
        expected_ids_read=[{DEVICE_SCHEMA_POOL_ID}],
        pools=(HOLDER_SCHEMA_POOL, POD_HOLDER_SCHEMA_POOL),
    ),
]


def site_name_renamed(schema: SchemaRoot) -> None:
    index = next(index for index, node in enumerate(schema.nodes) if node.kind == SCOPED_SITE.kind)
    site = schema.nodes[index].duplicate()
    site.get_attribute(name="name").name = "label"
    site.human_friendly_id = ["label__value"]
    site.display_label = "{{ label__value }}"
    schema.nodes[index] = site


def device_tags_renamed_with_no_declared_scope(schema: SchemaRoot) -> None:
    declare_on_device(None)(schema)
    device_tags_renamed(schema)


# A rename can only reach a declaration that names elements, so these read no pool.
UNDECLARED_RENAME_CASES = [
    AcceptedDeclarationCase(
        name="field-renamed-on-a-kind-without-number-pool",
        constraint_name="attribute.name.update",
        kind=SCOPED_SITE.kind,
        field_name="label",
        path_type=SchemaPathType.ATTRIBUTE,
        change=site_name_renamed,
        expected_ids_read=[],
    ),
    AcceptedDeclarationCase(
        name="field-renamed-on-a-kind-whose-number-pool-declares-no-scope",
        constraint_name="attribute.name.update",
        kind=DEVICE,
        field_name="labels",
        path_type=SchemaPathType.ATTRIBUTE,
        change=device_tags_renamed_with_no_declared_scope,
        expected_ids_read=[],
    ),
]


class TestAcceptedDeclarations:
    @staticmethod
    async def _check(case: AcceptedDeclarationCase) -> RecordingPoolSource:
        candidate_schema = declared_schema()
        case.change(candidate_schema)
        pool_source = RecordingPoolSource(pools=case.pools)
        checker = declared_checker(pool_source=pool_source)

        grouped_data_paths = await checker.check(
            declared_request(
                candidate=unvalidated_schema_branch(candidate_schema),
                constraint_name=case.constraint_name,
                kind=case.kind,
                field_name=case.field_name,
                path_type=case.path_type,
            )
        )

        assert [path for grouped in grouped_data_paths for path in grouped.get_all_data_paths()] == []
        assert pool_source.requested_kinds == []
        return pool_source

    @pytest.mark.parametrize("case", MATCHING_DECLARATION_CASES, ids=[case.name for case in MATCHING_DECLARATION_CASES])
    async def test_accepts_a_declaration_matching_the_stored_scope(self, case: AcceptedDeclarationCase) -> None:
        pool_source = await self._check(case=case)

        assert pool_source.requested_ids == case.expected_ids_read

    @pytest.mark.parametrize("case", MISSING_POOL_CASES, ids=[case.name for case in MISSING_POOL_CASES])
    async def test_validates_a_declaration_whose_pool_is_missing_as_a_new_one(
        self, case: AcceptedDeclarationCase
    ) -> None:
        pool_source = await self._check(case=case)

        assert pool_source.requested_ids == case.expected_ids_read

    @pytest.mark.parametrize("case", UNDECLARED_RENAME_CASES, ids=[case.name for case in UNDECLARED_RENAME_CASES])
    async def test_reads_no_pool_for_a_rename_no_declaration_names(self, case: AcceptedDeclarationCase) -> None:
        pool_source = await self._check(case=case)

        assert (pool_source.requested_ids, pool_source.requested_attributes) == ([], [])


@dataclass(frozen=True)
class MissingSchemaCase:
    name: str
    constraint_name: str
    field_name: str
    path_type: SchemaPathType
    candidate_change: Callable[[SchemaRoot], None]


# The candidate no longer defines the declaring kind or attribute, so no declaration is left to compare.
MISSING_SCHEMA_CASES = [
    MissingSchemaCase(
        name="declaring-kind-missing-from-the-candidate-schema",
        constraint_name=SCOPE_CONSTRAINT,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        candidate_change=without_device,
    ),
    MissingSchemaCase(
        name="declaring-attribute-missing-from-the-candidate-schema",
        constraint_name=SCOPE_CONSTRAINT,
        field_name="vlan_index",
        path_type=SchemaPathType.ATTRIBUTE,
        candidate_change=unchanged,
    ),
    MissingSchemaCase(
        name="renamed-field-of-a-kind-missing-from-the-candidate-schema",
        constraint_name="relationship.name.update",
        field_name="location",
        path_type=SchemaPathType.RELATIONSHIP,
        candidate_change=without_device,
    ),
]


class TestDeclaredScopeMissingSchema:
    """A change whose kind or attribute the candidate schema no longer defines leaves no declaration to compare.

    Removing a scope element or a kind is judged by the removal checks, not by the declaration rules.
    """

    @pytest.mark.parametrize("case", MISSING_SCHEMA_CASES, ids=[case.name for case in MISSING_SCHEMA_CASES])
    async def test_reports_no_violation_without_reading_pools(self, case: MissingSchemaCase) -> None:
        candidate_schema = declared_schema()
        case.candidate_change(candidate_schema)
        pool_source = RecordingPoolSource(pools=SCHEMA_POOLS)
        checker = declared_checker(pool_source=pool_source)
        node_schema = unvalidated_schema_branch(declared_schema()).get(name=DEVICE, duplicate=False)
        assert isinstance(node_schema, NodeSchema)
        request = SchemaConstraintValidatorRequest(
            branch=BRANCH,
            constraint_name=case.constraint_name,
            node_schema=node_schema,
            schema_path=SchemaPath(path_type=case.path_type, schema_kind=DEVICE, field_name=case.field_name),
            schema_branch=unvalidated_schema_branch(candidate_schema),
        )

        assert await checker.check(request) == []
        assert (pool_source.requested_kinds, pool_source.requested_ids) == ([], [])
