from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m047_backfill_or_null_display_label import Migration047
from infrahub.core.query.node import NodeListGetAttributeQuery
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


class TestMigration047(TestInfrahubApp):
    async def get_attribute_values_from_db(
        self, db: InfrahubDatabase, branch: Branch, node_ids: list[str]
    ) -> dict[str, str | None]:
        """Get display_label values from database for given node IDs."""
        query = await NodeListGetAttributeQuery.init(
            db=db, ids=node_ids, fields={"display_label": {True}}, branch=branch
        )
        await query.execute(db=db)
        node_attributes_map = query.get_attributes_group_by_node()
        result_map = {}
        for node_id in node_ids:
            if node_id not in node_attributes_map:
                result_map[node_id] = None
                continue
            result_map[node_id] = node_attributes_map[node_id].attrs["display_label"].value
        return result_map

    async def erase_display_label(self, db: InfrahubDatabase, node: Node) -> None:
        query = """
        MATCH (n:Node)-[:HAS_ATTRIBUTE]->(a:Attribute)
        WHERE n.uuid = $node_uuid AND a.name = "display_label"
        DETACH DELETE a
        """
        await db.execute_query(query=query, params={"node_uuid": node.id})

    async def test_migration_047_backfill_missing_display_label(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema,
        car_accord_main: Node,
        car_camry_main: Node,
    ) -> None:
        """Test that migration 047 backfills computed display_label for nodes with display_label in schema."""
        await self.erase_display_label(db=db, node=car_accord_main)
        await self.erase_display_label(db=db, node=car_camry_main)

        initial_values = await self.get_attribute_values_from_db(
            db=db, branch=default_branch, node_ids=[car_accord_main.id, car_camry_main.id]
        )
        assert initial_values[car_accord_main.id] is None
        assert initial_values[car_camry_main.id] is None

        async with db.start_session() as dbs:
            migration = Migration047()
            execution_result = await migration.execute(db=dbs)
            assert not execution_result.errors

            validation_result = await migration.validate_migration(db=dbs)
            assert not validation_result.errors

        final_values = await self.get_attribute_values_from_db(
            db=db, branch=default_branch, node_ids=[car_accord_main.id, car_camry_main.id]
        )

        assert final_values[car_accord_main.id] == "accord #444444"
        assert final_values[car_camry_main.id] == "camry #444444"

    async def test_migration_047_mixed_scenario(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema,
        car_accord_main: Node,
        car_camry_main: Node,
        person_john_main: Node,
    ) -> None:
        """Test migration with some nodes missing display_label and some having it."""
        await self.erase_display_label(db=db, node=person_john_main)

        initial_values = await self.get_attribute_values_from_db(
            db=db, branch=default_branch, node_ids=[car_accord_main.id, car_camry_main.id, person_john_main.id]
        )
        assert initial_values[car_accord_main.id] == "accord #444444"
        assert initial_values[car_camry_main.id] == "camry #444444"
        assert initial_values[person_john_main.id] is None

        async with db.start_session() as dbs:
            migration = Migration047()
            execution_result = await migration.execute(db=dbs)
            assert not execution_result.errors

        final_values = await self.get_attribute_values_from_db(
            db=db, branch=default_branch, node_ids=[car_accord_main.id, car_camry_main.id, person_john_main.id]
        )
        assert final_values[car_accord_main.id] == "accord #444444"
        assert final_values[car_camry_main.id] == "camry #444444"
        assert final_values[person_john_main.id] == "John"

    async def test_migration_047_idempotent(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema,
        car_accord_main: Node,
    ) -> None:
        """Test that running migration 047 multiple times doesn't cause issues."""
        node_ids = [car_accord_main.id]

        async with db.start_session() as dbs:
            migration = Migration047()
            execution_result = await migration.execute(db=dbs)
            assert not execution_result.errors

        first_values = await self.get_attribute_values_from_db(db=db, branch=default_branch, node_ids=node_ids)
        first_value = first_values[car_accord_main.id]

        async with db.start_session() as dbs:
            migration = Migration047()
            execution_result = await migration.execute(db=dbs)
            assert not execution_result.errors

        second_values = await self.get_attribute_values_from_db(db=db, branch=default_branch, node_ids=node_ids)
        assert second_values[car_accord_main.id] == first_value

    async def test_migration_047_execute_against_branch(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema,
        person_john_main: Node,
        person_jane_main: Node,
    ) -> None:
        await self.erase_display_label(db=db, node=person_john_main)
        await self.erase_display_label(db=db, node=person_jane_main)

        test_branch = await create_branch(db=db, branch_name="test-branch-m047")

        person_john_branch = await NodeManager.get_one(db=db, id=person_john_main.id, branch=test_branch)
        person_john_branch.height.value = 185
        await person_john_branch.save(db=db)

        person_jane_branch = await NodeManager.get_one(db=db, id=person_jane_main.id, branch=test_branch)
        person_jane_branch.height.value = 165
        await person_jane_branch.save(db=db)

        initial_values = await self.get_attribute_values_from_db(
            db=db, branch=test_branch, node_ids=[person_john_branch.id, person_jane_branch.id]
        )
        assert initial_values[person_john_branch.id] is None
        assert initial_values[person_jane_branch.id] is None

        async with db.start_session() as dbs:
            migration = Migration047()
            execution_result = await migration.execute_against_branch(db=dbs, branch=test_branch)
            assert not execution_result.errors

        branch_final_values = await self.get_attribute_values_from_db(
            db=db, branch=test_branch, node_ids=[person_john_branch.id, person_jane_branch.id]
        )
        assert branch_final_values[person_john_branch.id] == "John"
        assert branch_final_values[person_jane_branch.id] == "Jane"

        default_values = await self.get_attribute_values_from_db(
            db=db, branch=default_branch, node_ids=[person_john_main.id, person_jane_main.id]
        )
        assert default_values[person_john_main.id] is None
        assert default_values[person_jane_main.id] is None
