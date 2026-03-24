from pathlib import Path

import pytest

from infrahub.cli.db import load_export
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m041_deleted_dup_edges import Migration041
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.helpers.db_validation import verify_no_duplicate_paths


class TestMigration041:
    """Test Migration041 to delete duplicated edges after a merge that includes peers with updated kinds/inheritance
    - load a known bad data set, then massage it into a state that can be used by the migration and NodeManager
    - get the nodes before the migration
    - run the migration
    - verify the duplicate paths are all gone
    - get the nodes after the migration
    - verify the nodes attribute values and peers are the same
    """

    @pytest.fixture
    async def load_bad_data(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
    ) -> None:
        export_dir = Path(__file__).parent / ("data_export")
        await load_export(db=db, export_dir=export_dir)
        # set default branch on the import Root node
        query = """
MATCH (r:Root)
SET r.default_branch = "main"
        """
        await db.execute_query(query=query)
        # make the branch_level properties integers
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
        # delete the other Root created in the fixture chain
        query = """
MATCH (r:Root)
WHERE NOT exists((:TestPerson)-[:IS_PART_OF]->(r))
DETACH DELETE r
        """
        await db.execute_query(query=query)

    async def test_migration_041(self, db: InfrahubDatabase, load_bad_data, car_person_schema: SchemaBranch) -> None:
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

        expected_node_ids = [
            "18749df3-97b6-870c-43e8-1677b956a31e",
            "18749df4-3639-d70a-43ed-1677223041be",
            "18749df4-092d-b550-43e0-1677bd841482",
        ]
        deleted_node_ids = [
            "18749df4-38df-703f-43ed-1677fa762816",
        ]
        all_node_ids = expected_node_ids + deleted_node_ids
        before_nodes_map = await NodeManager.get_many(db=db, ids=all_node_ids, prefetch_relationships=True)
        assert set(before_nodes_map.keys()) == set(expected_node_ids)

        migration = Migration041()
        execution_result = await migration.execute(migration_input=MigrationInput(db=db))
        assert not execution_result.errors

        await verify_no_duplicate_paths(db=db)

        after_nodes_map = await NodeManager.get_many(
            db=db,
            ids=all_node_ids,
            prefetch_relationships=True,
        )
        assert set(after_nodes_map.keys()) == set(expected_node_ids)

        for node_id in expected_node_ids:
            before_node = before_nodes_map[node_id]
            after_node = after_nodes_map[node_id]
            # make sure we are getting the same Node from the database b/c the TestCar and Test2NewCar duplicates have the same UUID
            assert before_node.db_id == after_node.db_id
            for attr_name in before_node.get_schema().attribute_names:
                before_attr = getattr(before_node, attr_name)
                after_attr = getattr(after_node, attr_name)
                assert before_attr.value == after_attr.value
            for rel_name in before_node.get_schema().relationship_names:
                before_relm = getattr(before_node, rel_name)
                before_peers = await before_relm.get_peers(db=db)
                after_relm = getattr(after_node, rel_name)
                after_peers = await after_relm.get_peers(db=db)

                assert set(before_peers.keys()) == set(after_peers.keys())
                for peer_id in before_peers:
                    before_peer = before_peers[peer_id]
                    after_peer = after_peers[peer_id]
                    assert before_peer.db_id == after_peer.db_id
