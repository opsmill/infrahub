"""An IP pool keeps every value a live branch holds after a migration moves its namespace or its values to new vertices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import pytest

from infrahub.core import registry
from infrahub.core.constants import SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from tests.helpers.ip_pool import (
    ADDRESS_KIND,
    IP_POOL_CASES,
    PREFIX_KIND,
    IPPoolCase,
    create_namespace,
    create_pool,
    create_prefix,
    pool_on,
)
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

VRF_KIND = "TestVRF"
GENERIC_KIND = "TestLabelled"
VRF_SCHEMA = SchemaRoot(
    generics=[
        {"name": "Labelled", "namespace": "Test", "attributes": [{"name": "label", "kind": "Text", "optional": True}]}
    ],
    nodes=[{"name": "VRF", "namespace": "Test", "inherit_from": ["BuiltinIPNamespace"], "attributes": []}],
)


@dataclass
class MigratedPools:
    default_branch: Branch
    allocating_branch: Branch
    """The branch that allocates the second value: the branch that ran the migration."""
    pools: dict[str, Node]
    first_values: dict[str, str]


async def _add_generic(db: InfrahubDatabase, branch: Branch, kind: str) -> None:
    """The migration moves every node of `kind` on `branch` to a new vertex, and a branch forked earlier reads the old one."""
    schema = registry.schema.get_schema_branch(name=branch.name).duplicate()
    previous_schema = schema.get_node(name=kind, duplicate=True)
    new_schema = schema.get_node(name=kind, duplicate=True)
    new_schema.inherit_from = [*new_schema.inherit_from, GENERIC_KIND]
    schema.set(name=kind, schema=new_schema)
    schema.process()
    registry.schema.set_schema_branch(name=branch.name, schema=schema)
    branch.update_schema_hash()
    await branch.save(db=db)

    migration = NodeKindUpdateMigration(
        previous_node_schema=previous_schema,
        new_node_schema=schema.get_node(name=kind, duplicate=True),
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind=kind, field_name="inherit_from"),
    )
    result = await migration.execute(
        migration_input=MigrationInput(db=db, at=Timestamp(), user_id="migration-user"), branch=branch
    )
    assert not result.errors


async def _migrate_after_first_allocation(
    db: InfrahubDatabase, default_branch: Branch, migrated_kinds: list[str], migrate_on_branch: bool
) -> MigratedPools:
    """One pool per case in one VRF, each allocating its first value on main before the branch and the migration."""
    await load_schema(db=db, schema=VRF_SCHEMA)
    vrf = await create_namespace(db=db, name="vrf", kind=VRF_KIND)
    pools: dict[str, Node] = {}
    first_values: dict[str, str] = {}
    for case in IP_POOL_CASES:
        resource = await create_prefix(db=db, namespace=vrf, value=case.resource)
        pool = await create_pool(db=db, case=case, namespace=vrf, resources=[resource], name=f"pool-{case.name}")
        first_values[case.name] = case.value_of(await case.allocate(db=db, pool=pool, branch=default_branch))
        pools[case.name] = pool

    branch = await create_branch(db=db, branch_name="forked-before-migration")
    migrated_branch = branch if migrate_on_branch else default_branch
    for kind in migrated_kinds:
        await _add_generic(db=db, branch=migrated_branch, kind=kind)
    return MigratedPools(
        default_branch=default_branch, allocating_branch=migrated_branch, pools=pools, first_values=first_values
    )


@pytest.mark.usefixtures(
    "register_core_models_schema_scope_class", "register_ipam_schema_scope_class", "init_nodes_registry_scope_class"
)
class _NoValueAllocatedTwiceAfterKindMigration:
    migrated_kinds: ClassVar[list[str]]
    migrate_on_branch: ClassVar[bool]

    @pytest.fixture(scope="class")
    async def migrated_pools(self, db: InfrahubDatabase, default_branch_scope_class: Branch) -> MigratedPools:
        return await _migrate_after_first_allocation(
            db=db,
            default_branch=default_branch_scope_class,
            migrated_kinds=self.migrated_kinds,
            migrate_on_branch=self.migrate_on_branch,
        )

    @pytest.mark.parametrize("case", IP_POOL_CASES, ids=lambda case: case.name)
    async def test_main_does_not_receive_a_value_that_a_live_branch_holds(
        self, db: InfrahubDatabase, migrated_pools: MigratedPools, case: IPPoolCase
    ) -> None:
        """The branch that did not migrate reads the old vertices and the other one the new vertices."""
        pool = migrated_pools.pools[case.name]
        allocating_branch = migrated_pools.allocating_branch
        default_branch = migrated_pools.default_branch

        second = await case.allocate(
            db=db, pool=await pool_on(db=db, pool=pool, branch=allocating_branch), branch=allocating_branch
        )
        third = await case.allocate(
            db=db, pool=await pool_on(db=db, pool=pool, branch=default_branch), branch=default_branch
        )

        assert [migrated_pools.first_values[case.name], case.value_of(second), case.value_of(third)] == case.values(
            count=3
        )


class TestNamespaceKindMigratedOnMain(_NoValueAllocatedTwiceAfterKindMigration):
    migrated_kinds = [VRF_KIND]
    migrate_on_branch = False


class TestNamespaceKindMigratedOnBranch(_NoValueAllocatedTwiceAfterKindMigration):
    migrated_kinds = [VRF_KIND]
    migrate_on_branch = True


class TestAllocatedKindsMigratedOnMain(_NoValueAllocatedTwiceAfterKindMigration):
    migrated_kinds = [PREFIX_KIND, ADDRESS_KIND]
    migrate_on_branch = False


class TestAllocatedKindsMigratedOnBranch(_NoValueAllocatedTwiceAfterKindMigration):
    migrated_kinds = [PREFIX_KIND, ADDRESS_KIND]
    migrate_on_branch = True
