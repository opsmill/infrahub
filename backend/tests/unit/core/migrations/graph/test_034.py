from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m034_find_orphaned_schema_fields import Migration034
from infrahub.core.migrations.shared import MigrationInput
from infrahub.database import InfrahubDatabase
from tests.helpers.test_app import TestInfrahubApp


class TestMigration034(TestInfrahubApp):
    async def test_migration_034(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics
    ) -> None:
        main_schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        await registry.schema.load_schema_to_db(db=db, branch=default_branch, schema=main_schema_branch)
        main_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)

        branch1 = await create_branch(db=db, branch_name="test-branch-1")
        branch2 = await create_branch(db=db, branch_name="test-branch-2")

        car_generic = main_schema_branch.get_generic(name="TestCar", duplicate=False)
        person_node = main_schema_branch.get_node(name="TestPerson", duplicate=False)

        # delete car generic on branch1
        car_generic_node_branch1 = await NodeManager.get_one(db=db, branch=branch1, id=car_generic.get_id())
        await car_generic_node_branch1.delete(db=db)

        # delete person node on branch2
        person_node_node_branch2 = await NodeManager.get_one(db=db, branch=branch2, id=person_node.get_id())
        await person_node_node_branch2.delete(db=db)

        # delete person node on main
        person_node_node_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_node.get_id())
        await person_node_node_main.delete(db=db)

        # verify that attributes and relationships are still present on all branches for both car and person
        for branch in [branch1, branch2, default_branch]:
            for schema in [car_generic, person_node]:
                schema_field_ids = [field.get_id() for field in schema.attributes + schema.relationships]
                schema_field_nodes = await NodeManager.get_many(db=db, ids=schema_field_ids, branch=branch)
                assert len(schema_field_nodes) == len(schema_field_ids)

        # run the migration
        migration = Migration034()
        execution_result = await migration.execute(migration_input=MigrationInput(db=db))
        assert not execution_result.errors
        validation_result = await migration.validate_migration(db=db)
        assert not validation_result.errors

        # verify that car generic fields are deleted on branch 1
        schema_field_ids = [field.get_id() for field in car_generic.attributes + car_generic.relationships]
        schema_field_nodes = await NodeManager.get_many(db=db, ids=schema_field_ids, branch=branch1)
        assert len(schema_field_nodes) == 0

        # verify that person schema fields are not deleted on branch 1
        schema_field_ids = [field.get_id() for field in person_node.attributes + person_node.relationships]
        schema_field_nodes = await NodeManager.get_many(db=db, ids=schema_field_ids, branch=branch1)
        assert len(schema_field_nodes) == len(schema_field_ids)

        # verify that person schema fields are deleted on branch 2
        schema_field_ids = [field.get_id() for field in person_node.attributes + person_node.relationships]
        schema_field_nodes = await NodeManager.get_many(db=db, ids=schema_field_ids, branch=branch2)
        assert len(schema_field_nodes) == 0

        # verify that car generic fields are not deleted on branch 2
        schema_field_ids = [field.get_id() for field in car_generic.attributes + car_generic.relationships]
        schema_field_nodes = await NodeManager.get_many(db=db, ids=schema_field_ids, branch=branch2)
        assert len(schema_field_nodes) == len(schema_field_ids)

        # verify that person schema fields are deleted on main
        schema_field_ids = [field.get_id() for field in person_node.attributes + person_node.relationships]
        schema_field_nodes = await NodeManager.get_many(db=db, ids=schema_field_ids, branch=default_branch)
        assert len(schema_field_nodes) == 0

        # verify that car generic fields are not deleted on main
        schema_field_ids = [field.get_id() for field in car_generic.attributes + car_generic.relationships]
        schema_field_nodes = await NodeManager.get_many(db=db, ids=schema_field_ids, branch=default_branch)
        assert len(schema_field_nodes) == len(schema_field_ids)
