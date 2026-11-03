from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.api.schema import evaluate_candidate_schemas
from infrahub.core.constants import InfrahubKind
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.validators.aggregated_checker import AggregatedConstraintChecker
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.dependencies.registry import get_component_registry
from tests.helpers.number_pool import SCOPED_DEVICE, SCOPED_HOLDER, SCOPED_POD_HOLDER, SCOPED_POOL_SCHEMA
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

DEVICE_POOL = "device-vlan"


async def _pool(db: InfrahubDatabase, name: str, kind: str) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(db=db, name=name, node=kind, node_attribute="vlan_id", start_range=1, end_range=10)
    await pool.save(db=db)
    return pool


def _device(schema_branch: SchemaBranch) -> NodeSchema:
    device = schema_branch.get_node(name=SCOPED_DEVICE.kind)
    assert isinstance(device, NodeSchema)
    return device


def _device_renamed(schema_branch: SchemaBranch) -> SchemaRoot:
    device = _device(schema_branch)
    device.name = "Router"
    return SchemaRoot(nodes=[device])


def _vlan_id_renamed(schema_branch: SchemaBranch) -> SchemaRoot:
    device = _device(schema_branch)
    device.get_attribute(name="vlan_id").name = "vlan_number"
    return SchemaRoot(nodes=[device])


def _device_name_and_namespace_renamed(schema_branch: SchemaBranch) -> SchemaRoot:
    device = _device(schema_branch)
    device.name = "Router"
    device.namespace = "Lab"
    return SchemaRoot(nodes=[device])


def _device_and_vlan_id_renamed(schema_branch: SchemaBranch) -> SchemaRoot:
    device = _device(schema_branch)
    device.name = "Router"
    device.get_attribute(name="vlan_id").name = "vlan_number"
    return SchemaRoot(nodes=[device])


def _device_inherits_a_new_generic(schema_branch: SchemaBranch) -> SchemaRoot:
    device = _device(schema_branch)
    device.inherit_from = [*device.inherit_from, "ScopeTagged"]
    tagged = GenericSchema(
        name="Tagged", namespace="Scope", attributes=[AttributeSchema(name="tag", kind="Text", optional=True)]
    )
    return SchemaRoot(generics=[tagged], nodes=[device])


def _holder_renamed(schema_branch: SchemaBranch) -> SchemaRoot:
    holder = schema_branch.get_generic(name=SCOPED_HOLDER.kind)
    pod_holder = schema_branch.get_node(name=SCOPED_POD_HOLDER.kind)
    holder.name = "Base"
    pod_holder.inherit_from = ["ScopeBase"]
    return SchemaRoot(generics=[holder], nodes=[pod_holder])


def _role_renamed(schema_branch: SchemaBranch) -> SchemaRoot:
    device = _device(schema_branch)
    device.get_attribute(name="role").name = "function"
    return SchemaRoot(nodes=[device])


def _refusal(field: str, reason: str) -> str:
    return (
        f"'number_pool.rename' constraint violation on schema '{InfrahubKind.NUMBERPOOL}'. Node ({DEVICE_POOL}) is not"
        f" compliant. The error relates to field {field}='pool {DEVICE_POOL} allocates numbers for"
        f" ScopeDevice.vlan_id; {reason}'."
    )


class TestNumberPoolRenameSchemaChange:
    """Renames evaluated as a schema load evaluates them, against a pool saved once for the class."""

    @pytest.fixture(scope="class")
    async def device_pool(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> AsyncGenerator[CoreNumberPool]:
        await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setitem(registry.node, InfrahubKind.NUMBERPOOL, CoreNumberPool)
            yield await _pool(db=db, name=DEVICE_POOL, kind=SCOPED_DEVICE.kind)

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

    async def test_refuses_renaming_the_kind_a_pool_allocates_numbers_for(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_pool: CoreNumberPool
    ) -> None:
        violations = await self._violations(db=db, branch=default_branch_scope_class, change=_device_renamed)

        assert violations == [
            (
                device_pool.id,
                _refusal(field="name", reason="a kind cannot be renamed while a number pool allocates numbers for it"),
            )
        ]

    async def test_refuses_renaming_the_attribute_a_pool_allocates_numbers_for(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_pool: CoreNumberPool
    ) -> None:
        violations = await self._violations(db=db, branch=default_branch_scope_class, change=_vlan_id_renamed)

        assert violations == [
            (
                device_pool.id,
                _refusal(
                    field="vlan_number",
                    reason="an attribute cannot be renamed while a number pool allocates numbers for it",
                ),
            )
        ]

    @pytest.mark.parametrize(
        "change",
        [_device_name_and_namespace_renamed, _device_and_vlan_id_renamed],
        ids=["name-and-namespace", "kind-and-tracked-attribute"],
    )
    async def test_reports_the_pool_once_for_a_load_that_renames_the_kind_and_more(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_pool: CoreNumberPool,
        change: Callable[[SchemaBranch], SchemaRoot],
    ) -> None:
        """Such a load raises a constraint for each renamed property, and the pool is reported under the kind name."""
        violations = await self._violations(db=db, branch=default_branch_scope_class, change=change)

        assert violations == [
            (
                device_pool.id,
                _refusal(field="name", reason="a kind cannot be renamed while a number pool allocates numbers for it"),
            )
        ]

    async def test_refuses_making_the_kind_inherit_from_another_generic(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_pool: CoreNumberPool
    ) -> None:
        violations = await self._violations(
            db=db, branch=default_branch_scope_class, change=_device_inherits_a_new_generic
        )

        assert violations == [
            (
                device_pool.id,
                _refusal(
                    field="inherit_from",
                    reason="a kind cannot inherit from another generic while a number pool allocates numbers for it",
                ),
            )
        ]

    async def test_accepts_renaming_an_attribute_no_pool_allocates_numbers_for(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_pool: CoreNumberPool
    ) -> None:
        assert await self._violations(db=db, branch=default_branch_scope_class, change=_role_renamed) == []

    async def test_accepts_renaming_a_generic_when_only_a_kind_implementing_it_has_a_pool(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_pool: CoreNumberPool
    ) -> None:
        """The kind keeps its name and its generic, renamed, keeps its id, so the kind inherits from no other generic."""
        await _pool(db=db, name="pod-holder-vlan", kind=SCOPED_POD_HOLDER.kind)

        assert await self._violations(db=db, branch=default_branch_scope_class, change=_holder_renamed) == []
