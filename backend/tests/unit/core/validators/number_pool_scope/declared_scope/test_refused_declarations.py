"""Schema changes that a declared allocation scope refuses, compared with the scope its schema pool stores."""

from __future__ import annotations

import pytest

from infrahub.core.constants import InfrahubKind, PathType, SchemaPathType
from infrahub.core.registry import registry
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.validators.schema_branch.number_pool_scope_validator import DeclaredScopeComparator
from infrahub.pools.scope import ScopeElement
from tests.unit.core.validators.number_pool_scope.declared_scope.helpers import (
    CANNOT_CHANGE,
    DEVICE_SCHEMA_POOL,
    DEVICE_SCHEMA_POOL_ID,
    HOLDER_SCHEMA_POOL,
    HOLDER_SCHEMA_POOL_ID,
    POD_HOLDER_SCHEMA_POOL,
    POD_HOLDER_SCHEMA_POOL_ID,
    SCHEMA_POOLS,
    SCOPE_CONSTRAINT,
    UNSCOPED_DEVICE_SCHEMA_POOL,
    DeclarationCase,
    declaration_change,
    declare_on_device,
    declared_checker,
    declared_request,
    declared_schema,
    holder_declaration_cleared,
    holder_site_renamed,
    unvalidated_schema_branch,
    without_device,
)
from tests.unit.core.validators.number_pool_scope.helpers import (
    BRANCH,
    DEVICE,
    DEVICE_ROLE,
    DEVICE_SITE,
    HOLDER,
    RecordingPoolSource,
    device_of,
    device_role_renamed,
    device_site_renamed,
    scoped_pool,
    unchanged,
)

REFUSED_DECLARATION_CASES = [
    declaration_change(
        name="declaration-naming-another-element",
        scope=["site", "name"],
        expected=[(DEVICE_SCHEMA_POOL_ID, CANNOT_CHANGE)],
    ),
    declaration_change(
        name="declaration-dropping-an-element", scope=["site"], expected=[(DEVICE_SCHEMA_POOL_ID, CANNOT_CHANGE)]
    ),
    # The order of the elements is the order of each division's values, so reordering is a change.
    declaration_change(
        name="declaration-reordered", scope=["role", "site"], expected=[(DEVICE_SCHEMA_POOL_ID, CANNOT_CHANGE)]
    ),
    declaration_change(name="declaration-cleared", scope=[], expected=[(DEVICE_SCHEMA_POOL_ID, CANNOT_CHANGE)]),
    # A name matching no field and no stored element cannot be a rename, so it is a change.
    declaration_change(
        name="declaration-naming-no-element",
        scope=["site", "function"],
        expected=[(DEVICE_SCHEMA_POOL_ID, CANNOT_CHANGE)],
    ),
    # A pool created without a scope cannot get one later, so declaring one is a change.
    DeclarationCase(
        name="declaration-added-to-an-unscoped-pool",
        constraint_name=SCOPE_CONSTRAINT,
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=unchanged,
        expected=[(DEVICE_SCHEMA_POOL_ID, CANNOT_CHANGE)],
        expected_ids_read=[{DEVICE_SCHEMA_POOL_ID}],
        pools=(UNSCOPED_DEVICE_SCHEMA_POOL, HOLDER_SCHEMA_POOL),
    ),
    DeclarationCase(
        name="relationship-renamed-declaration-unchanged",
        constraint_name="relationship.name.update",
        kind=DEVICE,
        field_name="location",
        path_type=SchemaPathType.RELATIONSHIP,
        change=device_site_renamed,
        expected=[
            (
                DEVICE_SCHEMA_POOL_ID,
                'ScopeDevice.vlan_id: allocation_scope: "site" was renamed to "location";'
                " update allocation_scope to the new name",
            )
        ],
        expected_ids_read=[{DEVICE_SCHEMA_POOL_ID}],
    ),
    DeclarationCase(
        name="attribute-renamed-declaration-unchanged",
        constraint_name="attribute.name.update",
        kind=DEVICE,
        field_name="function",
        path_type=SchemaPathType.ATTRIBUTE,
        change=device_role_renamed,
        expected=[
            (
                DEVICE_SCHEMA_POOL_ID,
                'ScopeDevice.vlan_id: allocation_scope: "role" was renamed to "function";'
                " update allocation_scope to the new name",
            )
        ],
        expected_ids_read=[{DEVICE_SCHEMA_POOL_ID}],
    ),
    DeclarationCase(
        name="generic-relationship-renamed-declaration-unchanged",
        constraint_name="relationship.name.update",
        kind=HOLDER,
        field_name="location",
        path_type=SchemaPathType.RELATIONSHIP,
        change=holder_site_renamed,
        expected=[
            (
                HOLDER_SCHEMA_POOL_ID,
                'ScopeHolder.vlan_id: allocation_scope: "site" was renamed to "location";'
                " update allocation_scope to the new name",
            ),
            (
                POD_HOLDER_SCHEMA_POOL_ID,
                'ScopePodHolder.pod_number: allocation_scope: "site" was renamed to "location";'
                " update allocation_scope to the new name",
            ),
        ],
        expected_ids_read=[{HOLDER_SCHEMA_POOL_ID, POD_HOLDER_SCHEMA_POOL_ID}],
    ),
    DeclarationCase(
        name="generic-declaration-changed",
        constraint_name=SCOPE_CONSTRAINT,
        kind=HOLDER,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=holder_declaration_cleared,
        expected=[
            (HOLDER_SCHEMA_POOL_ID, "ScopeHolder.vlan_id: allocation_scope can't be changed after the pool is created")
        ],
        expected_ids_read=[{HOLDER_SCHEMA_POOL_ID}],
    ),
    # Without its pool the declaration is validated as a new one, which refuses a name matching no field.
    DeclarationCase(
        name="declaration-whose-pool-is-not-found-naming-no-element",
        constraint_name=SCOPE_CONSTRAINT,
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=declare_on_device(["site", "function"]),
        expected=[
            (
                DEVICE_SCHEMA_POOL_ID,
                'ScopeDevice.vlan_id: allocation_scope: "function" is not an attribute or a relationship of'
                " ScopeDevice on branch main",
            )
        ],
        expected_ids_read=[{DEVICE_SCHEMA_POOL_ID}],
        pools=(HOLDER_SCHEMA_POOL, POD_HOLDER_SCHEMA_POOL),
    ),
]


def test_the_comparator_names_a_rename_when_a_previous_schema_does_not_define_the_kind() -> None:
    candidate_schema = declared_schema()
    device_site_renamed(candidate_schema)
    # One schema before the change does not define the kind, as when the kind was added on the branch only.
    schema_without_device = declared_schema()
    without_device(schema_without_device)
    comparator = DeclaredScopeComparator(
        schema_branch=unvalidated_schema_branch(candidate_schema),
        previous_schemas=[
            unvalidated_schema_branch(schema_without_device, name=registry.default_branch),
            unvalidated_schema_branch(declared_schema()),
        ],
    )

    refusal = comparator.refusal(kind=DEVICE, entries=["site", "role"], stored=DEVICE_SCHEMA_POOL.scope)

    assert refusal == 'allocation_scope: "site" was renamed to "location"; update allocation_scope to the new name'


class TestRefusedDeclarations:
    @pytest.mark.parametrize("case", REFUSED_DECLARATION_CASES, ids=[case.name for case in REFUSED_DECLARATION_CASES])
    async def test_reports_the_schema_pool_whose_declaration_the_change_breaks(self, case: DeclarationCase) -> None:
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

        data_paths = [path for grouped in grouped_data_paths for path in grouped.get_all_data_paths()]
        assert [(path.node_id, path.value) for path in data_paths] == case.expected
        assert {(path.branch, path.path_type, path.kind, path.field_name) for path in data_paths} == (
            {(BRANCH.name, PathType.NODE, InfrahubKind.NUMBERPOOL, case.field_name)} if case.expected else set()
        )
        assert pool_source.requested_ids == case.expected_ids_read
        assert pool_source.requested_kinds == []

    async def test_compares_a_changed_declaration_with_its_schema_pool_when_the_attribute_holds_no_pool_id(
        self,
    ) -> None:
        """The pool can exist before its id is written into the attribute, so it is found by kind and attribute."""
        candidate_schema = declared_schema()
        declare_on_device(["site"])(candidate_schema)
        parameters = device_of(candidate_schema).get_attribute(name="vlan_id").parameters
        assert isinstance(parameters, NumberPoolParameters)
        parameters.number_pool_id = None
        pool_source = RecordingPoolSource(pools=SCHEMA_POOLS)
        checker = declared_checker(pool_source=pool_source)

        grouped_data_paths = await checker.check(
            declared_request(
                candidate=unvalidated_schema_branch(candidate_schema),
                constraint_name=SCOPE_CONSTRAINT,
                kind=DEVICE,
                field_name="vlan_id",
                path_type=SchemaPathType.ATTRIBUTE,
            )
        )

        data_paths = [path for grouped in grouped_data_paths for path in grouped.get_all_data_paths()]
        assert [(path.node_id, path.value) for path in data_paths] == [(DEVICE_SCHEMA_POOL_ID, CANNOT_CHANGE)]
        assert pool_source.requested_attributes == [{(DEVICE, "vlan_id")}]

    async def test_names_the_element_a_branch_renamed_after_the_default_branch_renamed_it(self) -> None:
        # The default branch renamed site to location, while a branch forked before that renames it to zone.
        default_schema = declared_schema()
        device_site_renamed(default_schema)
        declare_on_device(["location", "role"])(default_schema)
        candidate_schema = declared_schema()
        device_of(candidate_schema).get_relationship(name="site").name = "zone"
        location = ScopeElement(id=DEVICE_SITE.id, name="location")
        pool_source = RecordingPoolSource(
            pools=(scoped_pool(pool_id=DEVICE_SCHEMA_POOL_ID, kind=DEVICE, elements=(location, DEVICE_ROLE)),)
        )
        checker = declared_checker(pool_source=pool_source, default_schema=default_schema)

        grouped_data_paths = await checker.check(
            declared_request(
                candidate=unvalidated_schema_branch(candidate_schema),
                constraint_name="relationship.name.update",
                kind=DEVICE,
                field_name="zone",
                path_type=SchemaPathType.RELATIONSHIP,
            )
        )

        data_paths = [path for grouped in grouped_data_paths for path in grouped.get_all_data_paths()]
        assert [(path.node_id, path.value) for path in data_paths] == [
            (
                DEVICE_SCHEMA_POOL_ID,
                'ScopeDevice.vlan_id: allocation_scope: "site" was renamed to "zone";'
                " update allocation_scope to the new name",
            )
        ]
