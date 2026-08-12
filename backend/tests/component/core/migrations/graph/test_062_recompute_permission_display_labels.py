from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m062_recompute_permission_display_labels import Migration062
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.protocols import CoreObjectPermission
from infrahub.core.query.node import NodeListGetAttributeQuery
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestMigration062(TestInfrahubApp):
    async def get_display_label_from_db(
        self, db: InfrahubDatabase, branch: Branch, node_ids: list[str]
    ) -> dict[str, str | None]:
        query = await NodeListGetAttributeQuery.init(db=db, ids=node_ids, fields={"display_label": True}, branch=branch)
        await query.execute(db=db)
        node_attributes_map = query.get_attributes_group_by_node()
        result_map: dict[str, str | None] = {}
        for node_id in node_ids:
            if node_id not in node_attributes_map:
                result_map[node_id] = None
                continue
            result_map[node_id] = node_attributes_map[node_id].attrs["display_label"].value
        return result_map

    async def set_display_label_value(self, db: InfrahubDatabase, node_uuid: str, value: str) -> None:
        query = """
        MATCH (n:Node {uuid: $node_uuid})-[:HAS_ATTRIBUTE]->(a:Attribute {name: "display_label"})
        MATCH (a)-[hv:HAS_VALUE]->(av:AttributeValue)
        WHERE hv.status = "active" AND hv.to IS NULL
        SET av.value = $value
        """
        await db.execute_query(query=query, params={"node_uuid": node_uuid, "value": value})

    @pytest.fixture
    async def permissions_dataset(
        self, db: InfrahubDatabase, register_core_models_schema: SchemaBranch, default_branch: Branch
    ) -> dict[str, tuple[Node, str]]:
        permissions: dict[str, tuple[Node, str]] = {}

        for action, action_name in [
            (PermissionAction.ANY, "any"),
            (PermissionAction.VIEW, "view"),
            (PermissionAction.CREATE, "create"),
            (PermissionAction.UPDATE, "update"),
            (PermissionAction.DELETE, "delete"),
        ]:
            perm = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
            await perm.new(
                db=db,
                namespace="Test",
                name=f"Action{action.value}",
                action=action.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            )
            await perm.save(db=db)
            expected = f"object:Test:Action{action.value}:{action_name}:allow_all"
            permissions[perm.id] = (perm, expected)

        for decision, decision_name in [
            (PermissionDecision.DENY, "deny"),
            (PermissionDecision.ALLOW_DEFAULT, "allow_default"),
            (PermissionDecision.ALLOW_OTHER, "allow_other"),
            (PermissionDecision.ALLOW_ALL, "allow_all"),
        ]:
            perm = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
            await perm.new(
                db=db,
                namespace="Core",
                name=f"Decision{decision.value}",
                action=PermissionAction.VIEW.value,
                decision=decision.value,
            )
            await perm.save(db=db)
            expected = f"object:Core:Decision{decision.value}:view:{decision_name}"
            permissions[perm.id] = (perm, expected)

        for global_action, decision, decision_name in [
            (GlobalPermissions.MANAGE_ACCOUNTS, PermissionDecision.ALLOW_ALL, "allow_all"),
            (GlobalPermissions.MERGE_BRANCH, PermissionDecision.DENY, "deny"),
            (GlobalPermissions.MANAGE_SCHEMA, PermissionDecision.ALLOW_DEFAULT, "allow_default"),
        ]:
            perm = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
            await perm.new(db=db, action=global_action.value, decision=decision.value)
            await perm.save(db=db)
            expected = f"global:{global_action.value}:{decision_name}"
            permissions[perm.id] = (perm, expected)

        return permissions

    async def test_migration_062_recomputes_display_labels(
        self, db: InfrahubDatabase, default_branch: Branch, permissions_dataset: dict[str, tuple[Node, str]]
    ) -> None:
        for perm_id in permissions_dataset:
            await self.set_display_label_value(db=db, node_uuid=perm_id, value="old-value")

        all_ids = list(permissions_dataset)
        initial_values = await self.get_display_label_from_db(db=db, branch=default_branch, node_ids=all_ids)
        for perm_id in all_ids:
            assert initial_values[perm_id] == "old-value"

        async with db.start_session() as dbs:
            migration = Migration062()
            execution_result = await migration.execute(migration_input=MigrationInput(db=dbs))
            assert not execution_result.errors

            validation_result = await migration.validate_migration(db=dbs)
            assert not validation_result.errors

        final_values = await self.get_display_label_from_db(db=db, branch=default_branch, node_ids=all_ids)
        for perm_id, (_, expected) in permissions_dataset.items():
            assert final_values[perm_id] == expected, f"Expected {expected}, got {final_values[perm_id]}"

    async def test_migration_062_idempotent(
        self, db: InfrahubDatabase, default_branch: Branch, permissions_dataset: dict[str, tuple[Node, str]]
    ) -> None:
        all_ids = list(permissions_dataset)

        async with db.start_session() as dbs:
            migration = Migration062()
            execution_result = await migration.execute(migration_input=MigrationInput(db=dbs))
            assert not execution_result.errors

        first_values = await self.get_display_label_from_db(db=db, branch=default_branch, node_ids=all_ids)

        async with db.start_session() as dbs:
            migration = Migration062()
            execution_result = await migration.execute(migration_input=MigrationInput(db=dbs))
            assert not execution_result.errors

        second_values = await self.get_display_label_from_db(db=db, branch=default_branch, node_ids=all_ids)

        assert first_values == second_values

    async def test_migration_062_execute_against_branch(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
    ) -> None:
        obj_perm = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
        await obj_perm.new(
            db=db,
            namespace="Network",
            name="Interface",
            action=PermissionAction.UPDATE.value,
            decision=PermissionDecision.ALLOW_OTHER.value,
        )
        await obj_perm.save(db=db)
        await self.set_display_label_value(db=db, node_uuid=obj_perm.id, value="old-branch-value")

        test_branch = await create_branch(db=db, branch_name="test-branch-m062")

        obj_perm_branch = await NodeManager.get_one(
            db=db, kind=CoreObjectPermission, id=obj_perm.id, branch=test_branch, raise_on_error=True
        )
        obj_perm_branch.namespace.value = "Net"
        await obj_perm_branch.save(db=db)

        async with db.start_session() as dbs:
            migration = Migration062()
            await migration.execute(migration_input=MigrationInput(db=dbs))

        await test_branch.rebase(db=db)

        async with db.start_session() as dbs:
            migration = Migration062()
            execution_result = await migration.execute_against_branch(
                migration_input=MigrationInput(db=dbs), branch=test_branch
            )
            assert not execution_result.errors

        branch_values = await self.get_display_label_from_db(db=db, branch=test_branch, node_ids=[obj_perm.id])
        assert branch_values[obj_perm.id] == "object:Net:Interface:update:allow_other"
