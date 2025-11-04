from pathlib import Path

import pytest

from infrahub.cli.db import load_export
from infrahub.core.branch import Branch
from infrahub.core.migrations.graph.m041_deleted_dup_edges import Migration041
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.helpers.db_validation import verify_no_duplicate_paths


class TestMigration041:
    @pytest.fixture
    async def load_bad_data(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
    ):
        # await delete_all_nodes(db=db)
        export_dir = Path(__file__).parent / ("data_export")
        await load_export(db=db, export_dir=export_dir)
        # set default branch
        query = """
MATCH (r:Root)
SET r.default_branch = "main"
        """
        await db.execute_query(query=query)
        # # export does not include Branches and we need them for the migration
        # branch = Branch(
        #     name="main",
        #     status=BranchStatus.OPEN,
        #     hierarchy_level=2,
        #     is_default=True,
        #     sync_with_git=False,
        # )
        # await branch.save(db=db)

        query = """
MATCH ()-[e]->()
WHERE e.branch_level IS NOT NULL
SET e.branch_level = toInteger(e.branch_level)
        """
        await db.execute_query(query=query)
        # export does not include AttributeValue.value or Boolean.value, we need to set those for the value comparisons
        query = """
CALL () {
    MATCH (b:Boolean)
    SET b.value = TRUE
}
CALL () {
    MATCH (attr:Attribute)-[:HAS_VALUE]->(av:AttributeValue)
    WHERE attr.name IN ["nbr_seats", "height"]
    WITH DISTINCT av
    SET av.value = toInteger(rand() * 100)
}
CALL () {
    MATCH (attr:Attribute)-[:HAS_VALUE]->(av:AttributeValue)
    WHERE attr.name IN ["color"]
    WITH DISTINCT av
    SET av.value = substring(randomUuid(), 0, 7)
}
CALL () {
    MATCH (attr:Attribute)-[:HAS_VALUE]->(av:AttributeValue)
    WHERE attr.name IN ["is_electric"]
    WITH DISTINCT av
    SET av.value = toBoolean(toInteger(round(rand())))
}
CALL () {
    MATCH (attr:Attribute)-[:HAS_VALUE]->(av:AttributeValue)
    WHERE attr.name IN ["transmission"]
    WITH DISTINCT av
    SET av.value = ["manual", "automatic", "flintstone-feet"][toInteger(floor(rand() * 3))]
}
CALL () {
    MATCH (attr:Attribute)-[:HAS_VALUE]->(av:AttributeValue)
    WHERE NOT attr.name IN ["nbr_seats", "height", "color", "is_electric", "transmission"]
    WITH DISTINCT av
    SET av.value = randomUUID()
}
        """
        await db.execute_query(query=query)
        # delete the other Root
        query = """
MATCH (r:Root)
WHERE NOT exists((:TestPerson)-[:IS_PART_OF]->(r))
DETACH DELETE r
        """
        await db.execute_query(query=query)

    async def test_migration_041(self, db: InfrahubDatabase, load_bad_data, car_person_schema: SchemaBranch):
        for schema_name in car_person_schema.node_names:
            if schema_name == "TestCar":
                car_schema = car_person_schema.get(name=schema_name, duplicate=False)
                car_schema.name = "NewCar"
                car_schema.namespace = "Test2"
                db.schema.set(name="Test2NewCar", schema=car_schema)
            elif schema_name == "TestPerson":
                person_schema = car_person_schema.get(name="TestPerson", duplicate=False)
                cars_rel = person_schema.get_relationship("cars")
                cars_rel.peer = "Test2NewCar"
                cars_driven_rel = person_schema.get_relationship("cars_driven")
                cars_driven_rel.peer = "Test2NewCar"
                db.schema.set(name="Test2NewPerson", schema=person_schema)
            else:
                db.schema.set(name=schema_name, schema=car_person_schema.get(name=schema_name, duplicate=False))

        # before_nodes_map = await NodeManager.get_many(
        #     db=db,
        #     ids=[
        #         "18749df3-97b6-870c-43e8-1677b956a31e",
        #         "18749df4-3639-d70a-43ed-1677223041be",
        #         "18749df4-092d-b550-43e0-1677bd841482",
        #         "18749df4-38df-703f-43ed-1677fa762816",
        #     ],
        # )

        migration = Migration041()
        execution_result = await migration.execute(db=db)
        assert not execution_result.errors

        await verify_no_duplicate_paths(db=db)

        # TODO: verify node values and relationships are still correct
