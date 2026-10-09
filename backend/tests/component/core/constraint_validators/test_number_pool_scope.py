from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.api.schema import evaluate_candidate_schemas
from infrahub.core import registry
from infrahub.core.constants import HashableModelState, InfrahubKind, RelationshipCardinality
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.validators.aggregated_checker import AggregatedConstraintChecker
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.dependencies.registry import get_component_registry
from infrahub.pools.scope import AllocationScopeResolver
from tests.helpers.number_pool import SCOPED_DEVICE, SCOPED_HOLDER, SCOPED_POD_HOLDER, SCOPED_POOL_SCHEMA
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

DEVICE_POOL_BY_SITE = "vlan-per-site"
DEVICE_POOL_BY_ROLE = "vlan-per-role"
HOLDER_POOL_BY_SITE = "holder-vlan-per-site"


async def _scoped_pool(db: InfrahubDatabase, name: str, kind: str, scope: list[str]) -> CoreNumberPool:
    allocation_scope = AllocationScopeResolver(
        schema_branch=registry.schema.get_schema_branch(name=registry.default_branch)
    ).resolve(kind=kind, entries=scope)
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name=name,
        node=kind,
        node_attribute="vlan_id",
        start_range=1,
        end_range=10,
        allocation_scope=allocation_scope.to_stored(),
    )
    await pool.save(db=db)
    return pool


def _device(schema_branch: SchemaBranch) -> NodeSchema:
    device = schema_branch.get_node(name=SCOPED_DEVICE.kind)
    assert isinstance(device, NodeSchema)
    return device


def _site_optional(schema_branch: SchemaBranch) -> SchemaRoot:
    device = _device(schema_branch)
    device.get_relationship(name="site").optional = True
    return SchemaRoot(nodes=[device])


def _site_many(schema_branch: SchemaBranch) -> SchemaRoot:
    device = _device(schema_branch)
    site = device.get_relationship(name="site")
    site.cardinality = RelationshipCardinality.MANY
    # Processing sets max_count to 1 on a relationship of cardinality one, which a schema file leaves unset.
    site.max_count = 0
    return SchemaRoot(nodes=[device])


def _site_removed(schema_branch: SchemaBranch) -> SchemaRoot:
    device = _device(schema_branch)
    device.get_relationship(name="site").state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[device])


def _site_renamed(schema_branch: SchemaBranch) -> SchemaRoot:
    device = _device(schema_branch)
    device.get_relationship(name="site").name = "location"
    return SchemaRoot(nodes=[device])


def _role_optional(schema_branch: SchemaBranch) -> SchemaRoot:
    device = _device(schema_branch)
    device.get_attribute(name="role").optional = True
    return SchemaRoot(nodes=[device])


def _role_removed(schema_branch: SchemaBranch) -> SchemaRoot:
    device = _device(schema_branch)
    device.get_attribute(name="role").state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[device])


def _vlan_id_unique(schema_branch: SchemaBranch) -> SchemaRoot:
    device = _device(schema_branch)
    device.get_attribute(name="vlan_id").unique = True
    return SchemaRoot(nodes=[device])


def _holder_site_optional(schema_branch: SchemaBranch) -> SchemaRoot:
    holder = schema_branch.get_generic(name=SCOPED_HOLDER.kind)
    assert isinstance(holder, GenericSchema)
    holder.get_relationship(name="site").optional = True
    return SchemaRoot(generics=[holder])


def _pod_removed(schema_branch: SchemaBranch) -> SchemaRoot:
    pod_holder = schema_branch.get_node(name=SCOPED_POD_HOLDER.kind)
    assert isinstance(pod_holder, NodeSchema)
    pod_holder.get_attribute(name="pod").state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[pod_holder])


def _refusal(pool: str, field: str, detail: str) -> str:
    return (
        f"'number_pool.scope' constraint violation on schema '{InfrahubKind.NUMBERPOOL}'. Node ({pool}) is not"
        f" compliant. The error relates to field {field}='pool {pool} {detail}'."
    )


@dataclass(frozen=True)
class RefusalCase:
    name: str
    change: Callable[[SchemaBranch], SchemaRoot]
    pool: str
    field: str
    detail: str


@dataclass(frozen=True)
class AcceptedCase:
    name: str
    change: Callable[[SchemaBranch], SchemaRoot]


REFUSAL_CASES = [
    RefusalCase(
        name="relationship-made-optional",
        change=_site_optional,
        pool=DEVICE_POOL_BY_SITE,
        field="site",
        detail="divides its numbers by ScopeDevice.site; a scope element must stay required",
    ),
    RefusalCase(
        name="relationship-made-many",
        change=_site_many,
        pool=DEVICE_POOL_BY_SITE,
        field="site",
        detail="divides its numbers by ScopeDevice.site; a scope element must stay a relationship of cardinality one",
    ),
    RefusalCase(
        name="relationship-removed",
        change=_site_removed,
        pool=DEVICE_POOL_BY_SITE,
        field="site",
        detail="divides its numbers by ScopeDevice.site; a scope element cannot be removed while the pool exists",
    ),
    RefusalCase(
        name="attribute-made-optional",
        change=_role_optional,
        pool=DEVICE_POOL_BY_ROLE,
        field="role",
        detail="divides its numbers by ScopeDevice.role; a scope element must stay required",
    ),
    RefusalCase(
        name="attribute-removed",
        change=_role_removed,
        pool=DEVICE_POOL_BY_ROLE,
        field="role",
        detail="divides its numbers by ScopeDevice.role; a scope element cannot be removed while the pool exists",
    ),
    RefusalCase(
        name="generic-relationship-made-optional",
        change=_holder_site_optional,
        pool=HOLDER_POOL_BY_SITE,
        field="site",
        detail="divides its numbers by ScopeHolder.site; a scope element must stay required",
    ),
]

ACCEPTED_CASES = [
    AcceptedCase(name="relationship-renamed", change=_site_renamed),
    AcceptedCase(name="implementing-kind-element-removed", change=_pod_removed),
]


class TestNumberPoolScopeSchemaChange:
    """Schema changes evaluated as a schema load evaluates them, against scoped pools saved once for the class."""

    @pytest.fixture(scope="class")
    async def scoped_pools(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> dict[str, CoreNumberPool]:
        await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
        registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
        return {
            DEVICE_POOL_BY_SITE: await _scoped_pool(
                db=db, name=DEVICE_POOL_BY_SITE, kind=SCOPED_DEVICE.kind, scope=["site"]
            ),
            DEVICE_POOL_BY_ROLE: await _scoped_pool(
                db=db, name=DEVICE_POOL_BY_ROLE, kind=SCOPED_DEVICE.kind, scope=["role"]
            ),
            HOLDER_POOL_BY_SITE: await _scoped_pool(
                db=db, name=HOLDER_POOL_BY_SITE, kind=SCOPED_HOLDER.kind, scope=["site"]
            ),
        }

    @staticmethod
    async def _violations(
        db: InfrahubDatabase, branch: Branch, change: Callable[[SchemaBranch], SchemaRoot]
    ) -> list[tuple[str, str]]:
        branch_schema = registry.schema.get_schema_branch(name=branch.name)
        candidate_schema, result = evaluate_candidate_schemas(
            branch_schema=branch_schema, schemas_to_evaluate=[change(branch_schema.duplicate())]
        )
        checker = await get_component_registry().get_component(AggregatedConstraintChecker, db=db, branch=branch)

        violations: list[tuple[str, str]] = []
        for constraint in result.constraints:
            node_schema = candidate_schema.get(name=constraint.path.schema_kind, duplicate=False)
            assert isinstance(node_schema, NodeSchema | GenericSchema)
            request = SchemaConstraintValidatorRequest(
                branch=branch,
                constraint_name=constraint.constraint_name,
                node_schema=node_schema,
                schema_path=constraint.path,
                schema_branch=candidate_schema,
            )
            violations.extend(
                (violation.node_id, violation.message) for violation in await checker.run_constraints(request)
            )
        return violations

    @pytest.mark.parametrize("case", REFUSAL_CASES, ids=[case.name for case in REFUSAL_CASES])
    async def test_refuses_a_change_that_breaks_a_scope_element(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        scoped_pools: dict[str, CoreNumberPool],
        case: RefusalCase,
    ) -> None:
        violations = await self._violations(db=db, branch=default_branch_scope_class, change=case.change)

        assert violations == [
            (scoped_pools[case.pool].id, _refusal(pool=case.pool, field=case.field, detail=case.detail))
        ]

    async def test_refuses_making_the_tracked_attribute_unique(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, scoped_pools: dict[str, CoreNumberPool]
    ) -> None:
        violations = await self._violations(db=db, branch=default_branch_scope_class, change=_vlan_id_unique)

        detail = "allocates ScopeDevice.vlan_id per division; a globally unique number cannot be allocated per division"
        assert sorted(violations) == sorted(
            (scoped_pools[pool].id, _refusal(pool=pool, field="vlan_id", detail=detail))
            for pool in (DEVICE_POOL_BY_SITE, DEVICE_POOL_BY_ROLE)
        )

    @pytest.mark.parametrize("case", ACCEPTED_CASES, ids=[case.name for case in ACCEPTED_CASES])
    async def test_accepts_a_change_that_keeps_every_scope_element(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        scoped_pools: dict[str, CoreNumberPool],
        case: AcceptedCase,
    ) -> None:
        assert await self._violations(db=db, branch=default_branch_scope_class, change=case.change) == []

    async def test_renaming_a_scope_element_reaches_the_checker_under_its_new_name(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, scoped_pools: dict[str, CoreNumberPool]
    ) -> None:
        branch_schema = registry.schema.get_schema_branch(name=default_branch_scope_class.name)

        _, result = evaluate_candidate_schemas(
            branch_schema=branch_schema, schemas_to_evaluate=[_site_renamed(branch_schema.duplicate())]
        )

        # Constraints on other fields cannot reach a scope, so only the renamed field's are pinned.
        assert [
            (constraint.constraint_name, constraint.path.field_name)
            for constraint in result.constraints
            if constraint.path.field_name in {"site", "location"}
        ] == [("relationship.name.update", "location")]


async def test_a_pool_whose_stored_scope_cannot_be_read_only_refuses_the_fields_it_names(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    site_pool = await _scoped_pool(db=db, name=DEVICE_POOL_BY_SITE, kind=SCOPED_DEVICE.kind, scope=["site"])
    unreadable_pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await unreadable_pool.new(
        db=db,
        name="vlan-per-role-by-name",
        node=SCOPED_DEVICE.kind,
        node_attribute="vlan_id",
        start_range=1,
        end_range=10,
        allocation_scope=["role"],
    )
    await unreadable_pool.save(db=db)

    site_violations = await TestNumberPoolScopeSchemaChange._violations(
        db=db, branch=default_branch, change=_site_optional
    )
    role_violations = await TestNumberPoolScopeSchemaChange._violations(
        db=db, branch=default_branch, change=_role_optional
    )

    assert site_violations == [
        (
            site_pool.id,
            _refusal(
                pool=DEVICE_POOL_BY_SITE,
                field="site",
                detail="divides its numbers by ScopeDevice.site; a scope element must stay required",
            ),
        )
    ]
    assert role_violations == [
        (
            unreadable_pool.id,
            f"'number_pool.scope' constraint violation on schema '{InfrahubKind.NUMBERPOOL}'. Node"
            " (vlan-per-role-by-name) is not compliant. The error relates to field role='allocation_scope of pool"
            ' vlan-per-role-by-name: the stored entry "role" is not an element with an "id" and a "name"; recreate'
            " the pool to set its scope; the change to ScopeDevice.role cannot be checked against this pool'.",
        )
    ]
