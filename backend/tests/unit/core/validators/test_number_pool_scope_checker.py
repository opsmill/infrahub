from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, PathType, RelationshipCardinality, SchemaPathType
from infrahub.core.path import SchemaPath
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.pool.scope import NumberPoolScopeChecker
from infrahub.pools.scope import AllocationScope, ScopeElement
from infrahub.pools.scoped_number_pool_reader import NumberPoolScopes, ScopedNumberPool, UnreadableScopeNumberPool
from tests.helpers.number_pool import (
    SCOPED_DEVICE,
    SCOPED_HOLDER,
    SCOPED_LINK,
    SCOPED_POD_HOLDER,
    SCOPED_RACK,
    SCOPED_SITE,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

BRANCH = Branch(name="feature")

DEVICE = "ScopeDevice"
HOLDER = "ScopeHolder"
POD_HOLDER = "ScopePodHolder"

SUPPORTED_CONSTRAINT_NAMES = [
    "attribute.optional.update",
    "relationship.optional.update",
    "relationship.cardinality.update",
    "attribute.unique.update",
    "attribute.kind.update",
    "node.attribute.remove",
    "node.relationship.remove",
    "attribute.name.update",
    "relationship.name.update",
    "attribute.parameters.allocation_scope.update",
]


def _field_id(kind: str, name: str) -> str:
    return f"{kind}-{name}-id"


def _with_field_ids[SchemaT: (NodeSchema, GenericSchema)](schema: SchemaT) -> SchemaT:
    """Return a copy of the schema whose own fields hold the ids a saved schema gives them."""
    saved: SchemaT = copy.deepcopy(schema)
    for attribute in saved.attributes:
        attribute.id = _field_id(kind=saved.kind, name=attribute.name)
    for relationship in saved.relationships:
        relationship.id = _field_id(kind=saved.kind, name=relationship.name)
    return saved


def _saved_schema() -> SchemaRoot:
    return SchemaRoot(
        generics=[_with_field_ids(SCOPED_HOLDER)],
        nodes=[
            SCOPED_SITE,
            SCOPED_RACK,
            SCOPED_LINK,
            _with_field_ids(SCOPED_DEVICE),
            _with_field_ids(SCOPED_POD_HOLDER),
        ],
    )


def _schema_branch(schema: SchemaRoot, name: str = BRANCH.name) -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name=name)
    schema_branch.load_schema(schema=schema)
    schema_branch.process()
    return schema_branch


def _device(schema: SchemaRoot) -> NodeSchema:
    return next(node for node in schema.nodes if node.kind == DEVICE)


def _holder(schema: SchemaRoot) -> GenericSchema:
    return next(generic for generic in schema.generics if generic.kind == HOLDER)


def _unchanged(schema: SchemaRoot) -> None:
    del schema


def _device_site_optional(schema: SchemaRoot) -> None:
    _device(schema).get_relationship(name="site").optional = True


def _device_site_many(schema: SchemaRoot) -> None:
    _device(schema).get_relationship(name="site").cardinality = RelationshipCardinality.MANY


def _device_role_optional(schema: SchemaRoot) -> None:
    _device(schema).get_attribute(name="role").optional = True


def _device_vlan_id_unique(schema: SchemaRoot) -> None:
    _device(schema).get_attribute(name="vlan_id").unique = True


def _device_vlan_id_renamed_and_made_unique(schema: SchemaRoot) -> None:
    attribute = _device(schema).get_attribute(name="vlan_id")
    attribute.name = "vlan"
    attribute.unique = True


def _device_role_kind(kind: str) -> Callable[[SchemaRoot], None]:
    def change(schema: SchemaRoot) -> None:
        _device(schema).get_attribute(name="role").kind = kind

    return change


def _device_site_removed(schema: SchemaRoot) -> None:
    device = _device(schema)
    device.relationships = [relationship for relationship in device.relationships if relationship.name != "site"]


def _device_role_removed(schema: SchemaRoot) -> None:
    device = _device(schema)
    device.attributes = [attribute for attribute in device.attributes if attribute.name != "role"]


def _device_tags_removed(schema: SchemaRoot) -> None:
    device = _device(schema)
    device.attributes = [attribute for attribute in device.attributes if attribute.name != "tags"]


def _device_site_renamed(schema: SchemaRoot) -> None:
    _device(schema).get_relationship(name="site").name = "location"


def _device_role_renamed(schema: SchemaRoot) -> None:
    _device(schema).get_attribute(name="role").name = "function"


def _device_site_renamed_and_made_optional(schema: SchemaRoot) -> None:
    relationship = _device(schema).get_relationship(name="site")
    relationship.name = "location"
    relationship.optional = True


def _holder_site_optional(schema: SchemaRoot) -> None:
    _holder(schema).get_relationship(name="site").optional = True


def _pod_removed(schema: SchemaRoot) -> None:
    pod_holder = next(node for node in schema.nodes if node.kind == POD_HOLDER)
    pod_holder.attributes = [attribute for attribute in pod_holder.attributes if attribute.name != "pod"]


def _pool(pool_id: str, kind: str, elements: tuple[ScopeElement, ...]) -> ScopedNumberPool:
    return ScopedNumberPool(
        id=pool_id, name=pool_id, kind=kind, tracked_attribute="vlan_id", scope=AllocationScope(elements=elements)
    )


DEVICE_SITE = ScopeElement(id=_field_id(kind=DEVICE, name="site"), name="site")
DEVICE_ROLE = ScopeElement(id=_field_id(kind=DEVICE, name="role"), name="role")
HOLDER_SITE = ScopeElement(id=_field_id(kind=HOLDER, name="site"), name="site")

DEVICE_POOL_BY_SITE = _pool(pool_id="vlan-per-site", kind=DEVICE, elements=(DEVICE_SITE,))
DEVICE_POOL_BY_ROLE = _pool(pool_id="vlan-per-role", kind=DEVICE, elements=(DEVICE_ROLE,))
HOLDER_POOL_BY_SITE = _pool(pool_id="holder-per-site", kind=HOLDER, elements=(HOLDER_SITE,))
POD_HOLDER_POOL_BY_SITE = _pool(pool_id="pod-holder-per-site", kind=POD_HOLDER, elements=(HOLDER_SITE,))

ALL_POOLS = (DEVICE_POOL_BY_SITE, DEVICE_POOL_BY_ROLE, HOLDER_POOL_BY_SITE, POD_HOLDER_POOL_BY_SITE)

UNREADABLE_SITE_POOL = UnreadableScopeNumberPool(
    id="vlan-unreadable",
    name="vlan-unreadable",
    kind=DEVICE,
    tracked_attribute="vlan_id",
    stored_scope=["site"],
    reason='allocation_scope of pool vlan-unreadable: the stored entry "site" is not an element with an "id" and a'
    ' "name"; recreate the pool to set its scope',
)


def _unreadable_site_violation(field_name: str) -> tuple[str, str]:
    return (
        "vlan-unreadable",
        'allocation_scope of pool vlan-unreadable: the stored entry "site" is not an element with an "id" and a'
        f' "name"; recreate the pool to set its scope; the change to ScopeDevice.{field_name} cannot be checked'
        " against this pool",
    )


class RecordingPoolSource:
    """Serves the scoped pools of the requested kinds and records each request in order."""

    def __init__(
        self, pools: Iterable[ScopedNumberPool], unreadable_pools: Iterable[UnreadableScopeNumberPool] = ()
    ) -> None:
        self.pools = list(pools)
        self.unreadable_pools = list(unreadable_pools)
        self.requested_kinds: list[set[str]] = []
        self.requested_ids: list[set[str]] = []

    async def get_for_kinds(self, kinds: Iterable[str]) -> NumberPoolScopes:
        requested = set(kinds)
        self.requested_kinds.append(requested)
        return NumberPoolScopes(
            readable=[pool for pool in self.pools if pool.kind in requested],
            unreadable=[pool for pool in self.unreadable_pools if pool.kind in requested],
        )

    async def get_by_ids(self, ids: Iterable[str]) -> NumberPoolScopes:
        requested = set(ids)
        self.requested_ids.append(requested)
        return NumberPoolScopes(
            readable=[pool for pool in self.pools if pool.id in requested],
            unreadable=[pool for pool in self.unreadable_pools if pool.id in requested],
        )


class StaticSchemaSource:
    def __init__(self, schema_branch: SchemaBranch, default_branch_schema: SchemaBranch | None = None) -> None:
        self.schema_branch = schema_branch
        self.default_branch_schema = default_branch_schema

    def get_schema_branch(self, name: str) -> SchemaBranch:
        if name == registry.default_branch and self.default_branch_schema is not None:
            return self.default_branch_schema
        assert name == BRANCH.name
        return self.schema_branch


@dataclass(frozen=True)
class ViolationCase:
    name: str
    constraint_name: str
    kind: str
    field_name: str
    path_type: SchemaPathType
    change: Callable[[SchemaRoot], None]
    expected: list[tuple[str, str]]
    expected_kinds_read: list[set[str]]
    pools: tuple[ScopedNumberPool, ...] = field(default=ALL_POOLS)
    unreadable_pools: tuple[UnreadableScopeNumberPool, ...] = ()


VIOLATION_CASES = [
    ViolationCase(
        name="relationship-made-optional-with-an-unreadable-scope-naming-it",
        constraint_name="relationship.optional.update",
        kind=DEVICE,
        field_name="site",
        path_type=SchemaPathType.RELATIONSHIP,
        change=_device_site_optional,
        expected=[
            (
                "vlan-per-site",
                "pool vlan-per-site divides its numbers by ScopeDevice.site; a scope element must stay required",
            ),
            _unreadable_site_violation(field_name="site"),
        ],
        expected_kinds_read=[{DEVICE}],
        unreadable_pools=(UNREADABLE_SITE_POOL,),
    ),
    ViolationCase(
        name="attribute-made-optional-with-an-unreadable-scope-naming-another-field",
        constraint_name="attribute.optional.update",
        kind=DEVICE,
        field_name="role",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_device_role_optional,
        expected=[
            (
                "vlan-per-role",
                "pool vlan-per-role divides its numbers by ScopeDevice.role; a scope element must stay required",
            )
        ],
        expected_kinds_read=[{DEVICE}],
        unreadable_pools=(UNREADABLE_SITE_POOL,),
    ),
    ViolationCase(
        name="tracked-attribute-made-unique-with-an-unreadable-scope",
        constraint_name="attribute.unique.update",
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_device_vlan_id_unique,
        expected=[_unreadable_site_violation(field_name="vlan_id")],
        expected_kinds_read=[{DEVICE}],
        pools=(),
        unreadable_pools=(UNREADABLE_SITE_POOL,),
    ),
    ViolationCase(
        name="relationship-made-optional",
        constraint_name="relationship.optional.update",
        kind=DEVICE,
        field_name="site",
        path_type=SchemaPathType.RELATIONSHIP,
        change=_device_site_optional,
        expected=[
            (
                "vlan-per-site",
                "pool vlan-per-site divides its numbers by ScopeDevice.site; a scope element must stay required",
            )
        ],
        expected_kinds_read=[{DEVICE}],
    ),
    ViolationCase(
        name="relationship-staying-required",
        constraint_name="relationship.optional.update",
        kind=DEVICE,
        field_name="site",
        path_type=SchemaPathType.RELATIONSHIP,
        change=_unchanged,
        expected=[],
        expected_kinds_read=[],
    ),
    ViolationCase(
        name="attribute-made-optional",
        constraint_name="attribute.optional.update",
        kind=DEVICE,
        field_name="role",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_device_role_optional,
        expected=[
            (
                "vlan-per-role",
                "pool vlan-per-role divides its numbers by ScopeDevice.role; a scope element must stay required",
            )
        ],
        expected_kinds_read=[{DEVICE}],
    ),
    ViolationCase(
        name="relationship-renamed-and-made-optional",
        constraint_name="relationship.optional.update",
        kind=DEVICE,
        field_name="location",
        path_type=SchemaPathType.RELATIONSHIP,
        change=_device_site_renamed_and_made_optional,
        expected=[
            (
                "vlan-per-site",
                "pool vlan-per-site divides its numbers by ScopeDevice.location; a scope element must stay required",
            )
        ],
        expected_kinds_read=[{DEVICE}],
    ),
    ViolationCase(
        name="relationship-made-many",
        constraint_name="relationship.cardinality.update",
        kind=DEVICE,
        field_name="site",
        path_type=SchemaPathType.RELATIONSHIP,
        change=_device_site_many,
        expected=[
            (
                "vlan-per-site",
                "pool vlan-per-site divides its numbers by ScopeDevice.site;"
                " a scope element must stay a relationship of cardinality one",
            )
        ],
        expected_kinds_read=[{DEVICE}],
    ),
    ViolationCase(
        name="tracked-attribute-made-unique",
        constraint_name="attribute.unique.update",
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_device_vlan_id_unique,
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
    ViolationCase(
        name="tracked-attribute-renamed-and-made-unique",
        constraint_name="attribute.unique.update",
        kind=DEVICE,
        field_name="vlan",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_device_vlan_id_renamed_and_made_unique,
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
    ViolationCase(
        name="attribute-staying-not-unique",
        constraint_name="attribute.unique.update",
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_unchanged,
        expected=[],
        expected_kinds_read=[],
    ),
    *[
        ViolationCase(
            name=f"attribute-made-{kind.lower()}",
            constraint_name="attribute.kind.update",
            kind=DEVICE,
            field_name="role",
            path_type=SchemaPathType.ATTRIBUTE,
            change=_device_role_kind(kind),
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
    ViolationCase(
        name="attribute-made-another-scalar-kind",
        constraint_name="attribute.kind.update",
        kind=DEVICE,
        field_name="role",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_device_role_kind("Number"),
        expected=[],
        expected_kinds_read=[],
    ),
    ViolationCase(
        name="relationship-removed",
        constraint_name="node.relationship.remove",
        kind=DEVICE,
        field_name="site",
        path_type=SchemaPathType.RELATIONSHIP,
        change=_device_site_removed,
        expected=[
            (
                "vlan-per-site",
                "pool vlan-per-site divides its numbers by ScopeDevice.site;"
                " a scope element cannot be removed while the pool exists",
            )
        ],
        expected_kinds_read=[{DEVICE}],
    ),
    ViolationCase(
        name="attribute-removed",
        constraint_name="node.attribute.remove",
        kind=DEVICE,
        field_name="role",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_device_role_removed,
        expected=[
            (
                "vlan-per-role",
                "pool vlan-per-role divides its numbers by ScopeDevice.role;"
                " a scope element cannot be removed while the pool exists",
            )
        ],
        expected_kinds_read=[{DEVICE}],
    ),
    ViolationCase(
        name="attribute-outside-any-scope-removed",
        constraint_name="node.attribute.remove",
        kind=DEVICE,
        field_name="tags",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_device_tags_removed,
        expected=[],
        expected_kinds_read=[{DEVICE}],
    ),
    ViolationCase(
        name="relationship-renamed",
        constraint_name="relationship.name.update",
        kind=DEVICE,
        field_name="location",
        path_type=SchemaPathType.RELATIONSHIP,
        change=_device_site_renamed,
        expected=[],
        expected_kinds_read=[],
    ),
    ViolationCase(
        name="attribute-renamed",
        constraint_name="attribute.name.update",
        kind=DEVICE,
        field_name="function",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_device_role_renamed,
        expected=[],
        expected_kinds_read=[],
    ),
    ViolationCase(
        name="allocation-scope-declaration-changed",
        constraint_name="attribute.parameters.allocation_scope.update",
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_unchanged,
        expected=[],
        expected_kinds_read=[],
    ),
    ViolationCase(
        name="kind-without-scoped-pool",
        constraint_name="node.relationship.remove",
        kind=DEVICE,
        field_name="site",
        path_type=SchemaPathType.RELATIONSHIP,
        change=_device_site_removed,
        expected=[],
        expected_kinds_read=[{DEVICE}],
        pools=(),
    ),
    ViolationCase(
        name="generic-element-made-optional",
        constraint_name="relationship.optional.update",
        kind=HOLDER,
        field_name="site",
        path_type=SchemaPathType.RELATIONSHIP,
        change=_holder_site_optional,
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
    ViolationCase(
        name="element-of-implementing-kind-removed",
        constraint_name="node.attribute.remove",
        kind=POD_HOLDER,
        field_name="pod",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_pod_removed,
        expected=[],
        expected_kinds_read=[{POD_HOLDER, HOLDER}],
    ),
]


def _request(case: ViolationCase, candidate: SchemaBranch) -> SchemaConstraintValidatorRequest:
    node_schema = candidate.get(name=case.kind, duplicate=False)
    assert isinstance(node_schema, NodeSchema | GenericSchema)
    return SchemaConstraintValidatorRequest(
        branch=BRANCH,
        constraint_name=case.constraint_name,
        node_schema=node_schema,
        schema_path=SchemaPath(path_type=case.path_type, schema_kind=case.kind, field_name=case.field_name),
        schema_branch=candidate,
    )


class TestNumberPoolScopeChecker:
    @pytest.mark.parametrize("constraint_name", SUPPORTED_CONSTRAINT_NAMES)
    def test_supports_each_constraint_that_can_break_a_scope(self, constraint_name: str) -> None:
        checker = NumberPoolScopeChecker(
            pool_source=RecordingPoolSource(pools=[]),
            schema_source=StaticSchemaSource(schema_branch=_schema_branch(_saved_schema())),
        )
        request = _request(
            case=ViolationCase(
                name="supported",
                constraint_name=constraint_name,
                kind=DEVICE,
                field_name="site",
                path_type=SchemaPathType.RELATIONSHIP,
                change=_unchanged,
                expected=[],
                expected_kinds_read=[],
            ),
            candidate=_schema_branch(_saved_schema()),
        )

        assert checker.supports(request)

    @pytest.mark.parametrize(
        "constraint_name", ["attribute.regex.update", "relationship.peer.update", "node.attribute.add"]
    )
    def test_ignores_a_constraint_that_cannot_break_a_scope(self, constraint_name: str) -> None:
        checker = NumberPoolScopeChecker(
            pool_source=RecordingPoolSource(pools=[]),
            schema_source=StaticSchemaSource(schema_branch=_schema_branch(_saved_schema())),
        )
        request = _request(
            case=ViolationCase(
                name="unsupported",
                constraint_name=constraint_name,
                kind=DEVICE,
                field_name="site",
                path_type=SchemaPathType.RELATIONSHIP,
                change=_unchanged,
                expected=[],
                expected_kinds_read=[],
            ),
            candidate=_schema_branch(_saved_schema()),
        )

        assert not checker.supports(request)

    @pytest.mark.parametrize("case", VIOLATION_CASES, ids=[case.name for case in VIOLATION_CASES])
    async def test_reports_one_violation_per_dependent_pool(self, case: ViolationCase) -> None:
        candidate_schema = _saved_schema()
        case.change(candidate_schema)
        pool_source = RecordingPoolSource(pools=case.pools, unreadable_pools=case.unreadable_pools)
        checker = NumberPoolScopeChecker(
            pool_source=pool_source,
            schema_source=StaticSchemaSource(schema_branch=_schema_branch(_saved_schema())),
        )

        grouped_data_paths = await checker.check(_request(case=case, candidate=_schema_branch(candidate_schema)))

        data_paths = [path for grouped in grouped_data_paths for path in grouped.get_all_data_paths()]
        assert [(path.node_id, path.value) for path in data_paths] == case.expected
        assert {(path.branch, path.path_type, path.kind, path.field_name) for path in data_paths} == (
            {(BRANCH.name, PathType.NODE, InfrahubKind.NUMBERPOOL, case.field_name)} if case.expected else set()
        )
        assert pool_source.requested_kinds == case.expected_kinds_read


DEVICE_SCHEMA_POOL_ID = "device-schema-pool"
HOLDER_SCHEMA_POOL_ID = "holder-schema-pool"
POD_HOLDER_SCHEMA_POOL_ID = "pod-holder-schema-pool"


def _with_pooled_attribute[SchemaT: (NodeSchema, GenericSchema)](
    schema: SchemaT, scope: list[str], pool_id: str, name: str = "vlan_id"
) -> SchemaT:
    """Return a copy of the schema whose attribute is the NumberPool attribute of a pool the schema created."""
    pooled: SchemaT = copy.deepcopy(schema)
    pooled.attributes = [attribute for attribute in pooled.attributes if attribute.name != name]
    pooled.attributes.append(
        AttributeSchema(
            name=name,
            kind="NumberPool",
            optional=False,
            read_only=True,
            parameters=NumberPoolParameters(
                start_range=1, end_range=100, allocation_scope=scope, number_pool_id=pool_id
            ),
        )
    )
    return pooled


def _declared_schema() -> SchemaRoot:
    return SchemaRoot(
        generics=[
            _with_field_ids(_with_pooled_attribute(SCOPED_HOLDER, scope=["site"], pool_id=HOLDER_SCHEMA_POOL_ID))
        ],
        nodes=[
            SCOPED_SITE,
            SCOPED_RACK,
            SCOPED_LINK,
            _with_field_ids(
                _with_pooled_attribute(SCOPED_DEVICE, scope=["site", "role"], pool_id=DEVICE_SCHEMA_POOL_ID)
            ),
            _with_field_ids(
                _with_pooled_attribute(
                    SCOPED_POD_HOLDER, scope=["site"], pool_id=POD_HOLDER_SCHEMA_POOL_ID, name="pod_number"
                )
            ),
        ],
    )


def _unvalidated_schema_branch(schema: SchemaRoot, name: str = BRANCH.name) -> SchemaBranch:
    """Return the schema as a load holds it before validation, which would need a default branch's schema."""
    schema_branch = SchemaBranch(cache={}, name=name)
    schema_branch.load_schema(schema=schema)
    schema_branch.process(validate_schema=False)
    return schema_branch


def _declare_on_device(scope: list[str]) -> Callable[[SchemaRoot], None]:
    def change(schema: SchemaRoot) -> None:
        parameters = _device(schema).get_attribute(name="vlan_id").parameters
        assert isinstance(parameters, NumberPoolParameters)
        parameters.allocation_scope = scope

    return change


def _holder_declaration_cleared(schema: SchemaRoot) -> None:
    parameters = _holder(schema).get_attribute(name="vlan_id").parameters
    assert isinstance(parameters, NumberPoolParameters)
    parameters.allocation_scope = []


def _device_site_renamed_and_declared(schema: SchemaRoot) -> None:
    _device_site_renamed(schema)
    _declare_on_device(["location", "role"])(schema)


DEVICE_SCHEMA_POOL = _pool(pool_id=DEVICE_SCHEMA_POOL_ID, kind=DEVICE, elements=(DEVICE_SITE, DEVICE_ROLE))
HOLDER_SCHEMA_POOL = _pool(pool_id=HOLDER_SCHEMA_POOL_ID, kind=HOLDER, elements=(HOLDER_SITE,))
POD_HOLDER_SCHEMA_POOL = _pool(pool_id=POD_HOLDER_SCHEMA_POOL_ID, kind=POD_HOLDER, elements=(HOLDER_SITE,))
UNSCOPED_DEVICE_SCHEMA_POOL = _pool(pool_id=DEVICE_SCHEMA_POOL_ID, kind=DEVICE, elements=())

SCHEMA_POOLS = (DEVICE_SCHEMA_POOL, HOLDER_SCHEMA_POOL, POD_HOLDER_SCHEMA_POOL)

UNREADABLE_DEVICE_SCHEMA_POOL = UnreadableScopeNumberPool(
    id=DEVICE_SCHEMA_POOL_ID,
    name=DEVICE_SCHEMA_POOL_ID,
    kind=DEVICE,
    tracked_attribute="vlan_id",
    stored_scope=["site", "role"],
    reason=f'allocation_scope of pool {DEVICE_SCHEMA_POOL_ID}: the stored entry "site" is not an element with an "id"'
    ' and a "name"; recreate the pool to set its scope',
)


def _unreadable_device_schema_pool_violation(field_name: str) -> tuple[str, str]:
    return (
        DEVICE_SCHEMA_POOL_ID,
        f'ScopeDevice.vlan_id: allocation_scope of pool {DEVICE_SCHEMA_POOL_ID}: the stored entry "site" is not an'
        ' element with an "id" and a "name"; recreate the pool to set its scope; the change to'
        f" ScopeDevice.{field_name} cannot be checked against this pool",
    )


CANNOT_CHANGE = "ScopeDevice.vlan_id: allocation_scope can't be changed after the pool is created"
SCOPE_CONSTRAINT = "attribute.parameters.allocation_scope.update"


@dataclass(frozen=True)
class DeclarationCase:
    name: str
    constraint_name: str
    kind: str
    field_name: str
    path_type: SchemaPathType
    change: Callable[[SchemaRoot], None]
    expected: list[tuple[str, str]]
    expected_ids_read: list[set[str]]
    pools: tuple[ScopedNumberPool, ...] = field(default=SCHEMA_POOLS)
    unreadable_pools: tuple[UnreadableScopeNumberPool, ...] = ()


def _declaration_change(name: str, scope: list[str], expected: list[tuple[str, str]]) -> DeclarationCase:
    return DeclarationCase(
        name=name,
        constraint_name=SCOPE_CONSTRAINT,
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_declare_on_device(scope),
        expected=expected,
        expected_ids_read=[{DEVICE_SCHEMA_POOL_ID}],
    )


DECLARATION_CASES = [
    DeclarationCase(
        name="declaration-changed-on-an-unreadable-scope",
        constraint_name=SCOPE_CONSTRAINT,
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_declare_on_device(["site"]),
        expected=[_unreadable_device_schema_pool_violation(field_name="vlan_id")],
        expected_ids_read=[{DEVICE_SCHEMA_POOL_ID}],
        pools=(HOLDER_SCHEMA_POOL, POD_HOLDER_SCHEMA_POOL),
        unreadable_pools=(UNREADABLE_DEVICE_SCHEMA_POOL,),
    ),
    _declaration_change(name="declaration-unchanged", scope=["site", "role"], expected=[]),
    _declaration_change(
        name="declaration-naming-another-element",
        scope=["site", "name"],
        expected=[(DEVICE_SCHEMA_POOL_ID, CANNOT_CHANGE)],
    ),
    _declaration_change(
        name="declaration-dropping-an-element", scope=["site"], expected=[(DEVICE_SCHEMA_POOL_ID, CANNOT_CHANGE)]
    ),
    _declaration_change(
        name="declaration-reordered", scope=["role", "site"], expected=[(DEVICE_SCHEMA_POOL_ID, CANNOT_CHANGE)]
    ),
    _declaration_change(name="declaration-cleared", scope=[], expected=[(DEVICE_SCHEMA_POOL_ID, CANNOT_CHANGE)]),
    _declaration_change(
        name="declaration-naming-no-element",
        scope=["site", "function"],
        expected=[(DEVICE_SCHEMA_POOL_ID, CANNOT_CHANGE)],
    ),
    DeclarationCase(
        name="declaration-added-to-an-unscoped-pool",
        constraint_name=SCOPE_CONSTRAINT,
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_unchanged,
        expected=[(DEVICE_SCHEMA_POOL_ID, CANNOT_CHANGE)],
        expected_ids_read=[{DEVICE_SCHEMA_POOL_ID}],
        pools=(UNSCOPED_DEVICE_SCHEMA_POOL, HOLDER_SCHEMA_POOL),
    ),
    DeclarationCase(
        name="relationship-renamed-declaration-following-under-the-declaration",
        constraint_name=SCOPE_CONSTRAINT,
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_device_site_renamed_and_declared,
        expected=[],
        expected_ids_read=[{DEVICE_SCHEMA_POOL_ID}],
    ),
    DeclarationCase(
        name="declaration-whose-pool-is-not-found",
        constraint_name=SCOPE_CONSTRAINT,
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_declare_on_device(["site"]),
        expected=[],
        expected_ids_read=[{DEVICE_SCHEMA_POOL_ID}],
        pools=(HOLDER_SCHEMA_POOL, POD_HOLDER_SCHEMA_POOL),
    ),
    DeclarationCase(
        name="generic-declaration-changed",
        constraint_name=SCOPE_CONSTRAINT,
        kind=HOLDER,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_holder_declaration_cleared,
        expected=[
            (HOLDER_SCHEMA_POOL_ID, "ScopeHolder.vlan_id: allocation_scope can't be changed after the pool is created")
        ],
        expected_ids_read=[{HOLDER_SCHEMA_POOL_ID}],
    ),
    DeclarationCase(
        name="generic-declaration-changed-seen-on-an-implementing-kind",
        constraint_name=SCOPE_CONSTRAINT,
        kind=POD_HOLDER,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=_holder_declaration_cleared,
        expected=[],
        expected_ids_read=[],
    ),
]


class TestNumberPoolScopeCheckerDeclaredScope:
    """Schema changes on kinds whose NumberPool attribute declares the scope of the pool the schema created."""

    @pytest.mark.parametrize("case", DECLARATION_CASES, ids=[case.name for case in DECLARATION_CASES])
    async def test_compares_the_declaration_with_the_stored_scope_by_id(self, case: DeclarationCase) -> None:
        candidate_schema = _declared_schema()
        case.change(candidate_schema)
        pool_source = RecordingPoolSource(pools=case.pools, unreadable_pools=case.unreadable_pools)
        checker = NumberPoolScopeChecker(
            pool_source=pool_source,
            schema_source=StaticSchemaSource(
                schema_branch=_unvalidated_schema_branch(_declared_schema()),
                default_branch_schema=_unvalidated_schema_branch(_declared_schema(), name=registry.default_branch),
            ),
        )
        candidate = _unvalidated_schema_branch(candidate_schema)
        node_schema = candidate.get(name=case.kind, duplicate=False)
        assert isinstance(node_schema, NodeSchema | GenericSchema)
        request = SchemaConstraintValidatorRequest(
            branch=BRANCH,
            constraint_name=case.constraint_name,
            node_schema=node_schema,
            schema_path=SchemaPath(path_type=case.path_type, schema_kind=case.kind, field_name=case.field_name),
            schema_branch=candidate,
        )

        grouped_data_paths = await checker.check(request)

        data_paths = [path for grouped in grouped_data_paths for path in grouped.get_all_data_paths()]
        assert [(path.node_id, path.value) for path in data_paths] == case.expected
        assert {(path.branch, path.path_type, path.kind, path.field_name) for path in data_paths} == (
            {(BRANCH.name, PathType.NODE, InfrahubKind.NUMBERPOOL, case.field_name)} if case.expected else set()
        )
        assert pool_source.requested_ids == case.expected_ids_read
        assert pool_source.requested_kinds == []


class TestNumberPoolScopeCheckerCandidateOnDestination:
    """A proposed change or a merge builds the candidate on the destination's schema and checks it for the source."""

    async def test_reports_a_pool_of_the_destination_scoped_by_a_field_the_source_removed(self) -> None:
        source_schema = _saved_schema()
        _device_site_removed(source_schema)
        candidate_schema = _saved_schema()
        _device_site_removed(candidate_schema)
        pool_source = RecordingPoolSource(pools=ALL_POOLS)
        checker = NumberPoolScopeChecker(
            pool_source=pool_source,
            schema_source=StaticSchemaSource(
                schema_branch=_schema_branch(source_schema),
                default_branch_schema=_schema_branch(_saved_schema(), name=registry.default_branch),
            ),
        )
        candidate = _schema_branch(candidate_schema, name=registry.default_branch)
        node_schema = candidate.get(name=DEVICE, duplicate=False)
        assert isinstance(node_schema, NodeSchema)
        request = SchemaConstraintValidatorRequest(
            branch=BRANCH,
            constraint_name="node.relationship.remove",
            node_schema=node_schema,
            schema_path=SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind=DEVICE, field_name="site"),
            schema_branch=candidate,
        )

        grouped_data_paths = await checker.check(request)

        data_paths = [path for grouped in grouped_data_paths for path in grouped.get_all_data_paths()]
        assert [(path.node_id, path.value) for path in data_paths] == [
            (
                "vlan-per-site",
                "pool vlan-per-site divides its numbers by ScopeDevice.site;"
                " a scope element cannot be removed while the pool exists",
            )
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


class TestNumberPoolScopeCheckerUnchangedField:
    """A proposed change or a merge also raises these constraints for the data changed on a field the schema keeps."""

    @pytest.mark.parametrize("case", UNCHANGED_FIELD_CASES, ids=[case.name for case in UNCHANGED_FIELD_CASES])
    async def test_reports_no_violation_without_reading_pools(self, case: UnchangedFieldCase) -> None:
        pool_source = RecordingPoolSource(pools=ALL_POOLS)
        checker = NumberPoolScopeChecker(
            pool_source=pool_source,
            schema_source=StaticSchemaSource(schema_branch=_schema_branch(_saved_schema())),
        )
        request = _request(
            case=ViolationCase(
                name=case.name,
                constraint_name=case.constraint_name,
                kind=DEVICE,
                field_name=case.field_name,
                path_type=case.path_type,
                change=_unchanged,
                expected=[],
                expected_kinds_read=[],
            ),
            candidate=_schema_branch(_saved_schema()),
        )

        assert await checker.check(request) == []
        assert pool_source.requested_kinds == []
