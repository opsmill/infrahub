from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m020_duplicate_edges import Migration020
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


class TestDuplicateEdgesDeleted:
    the_value = 122

    async def test_duplicate_edges_migration(self, db: InfrahubDatabase, car_person_schema: SchemaBranch) -> None:
        unchanged_node = await Node.init(db=db, schema="TestPerson")
        await unchanged_node.new(db=db, name="Unchanged", height=self.the_value)
        await unchanged_node.save(db=db)

        # create 4 duplicate AttributeValue nodes
        query = """
        UNWIND [1,2,3,4] AS i
        CREATE (:AttributeValue {value: $value, is_default: False})
        """
        await db.execute_query(query=query, params={"value": self.the_value})

        node_to_update = await Node.init(db=db, schema="TestPerson")
        await node_to_update.new(db=db, name="Update", height=self.the_value + 1)
        await node_to_update.save(db=db)

        node_to_delete = await Node.init(db=db, schema="TestPerson")
        await node_to_delete.new(db=db, name="Delete", height=self.the_value)
        await node_to_delete.save(db=db)

        # add duplicate edges
        query = """
        MATCH (n:Node)
        WHERE n.uuid IN $uuids
        MATCH (n)-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
        MATCH (a)-[e:HAS_VALUE]->(:AttributeValue {value: $the_value})
        MATCH (av:AttributeValue {value: $the_value})
        WHERE NOT exists((a)-[:HAS_VALUE]->(av))
        CREATE (a)-[duplicate_e:HAS_VALUE]->(av)
        SET duplicate_e = properties(e)
        WITH a
        CALL (a) {
            MATCH (a)-[pe:IS_PROTECTED]->(p)
            WITH a, pe, p
            LIMIT 1
            CREATE (a)-[new_pe:IS_PROTECTED]->(p)
            SET new_pe = properties(pe)
        }
        """
        await db.execute_query(
            query=query,
            params={
                "uuids": [unchanged_node.get_id(), node_to_update.get_id(), node_to_delete.get_id()],
                "attribute_name": "height",
                "the_value": self.the_value,
            },
        )

        # make the node changes
        node_to_update.height.value = self.the_value
        await node_to_update.save(db=db)
        before_delete = Timestamp()
        await node_to_delete.delete(db=db)

        # run the migration
        migration = Migration020()
        await migration.execute(db=db)
        await migration.validate_migration(db=db)

        # validate no duplicate edges
        for node in (unchanged_node, node_to_update, node_to_delete):
            await self._validate_no_duplicate_edges(db=db, node=node, attribute_name="height")

        # validate nodes are in correct state
        retrieved_unchanged_node = await NodeManager.get_one(db=db, id=unchanged_node.id)
        assert retrieved_unchanged_node.name.value == unchanged_node.name.value
        assert retrieved_unchanged_node.height.value == unchanged_node.height.value
        retrieved_updated_node = await NodeManager.get_one(db=db, id=node_to_update.id)
        assert retrieved_updated_node.name.value == node_to_update.name.value
        assert retrieved_updated_node.height.value == node_to_update.height.value
        assert await NodeManager.get_one(db=db, id=node_to_delete.id) is None
        retrieved_deleted_node = await NodeManager.get_one(db=db, id=node_to_delete.id, at=before_delete)
        assert retrieved_deleted_node.name.value == node_to_delete.name.value
        assert retrieved_deleted_node.height.value == node_to_delete.height.value

    async def _validate_no_duplicate_edges(self, db: InfrahubDatabase, node: Node, attribute_name: str) -> None:
        # validate that this node
        #  - does not have duplicate HAS_VALUE or IS_PROTECTED edges
        #  - only connects to one AttributeValue node even though multiple exist
        params = {"node_id": node.get_id(), "attribute_name": attribute_name}
        query = """
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
        WITH a
        LIMIT 1
        MATCH (a)-[e]-(p)
        RETURN a, type(e) AS edge_type, e.branch AS branch, e.status AS status, e.from AS from, e.to AS to, p.value AS value, COUNT(*) AS num_edges
        """
        results = await db.execute_query(query=query, params=params)
        for result in results:
            edge_type = result.get("edge_type")
            value = result.get("value")
            num_edges = result.get("num_edges")
            assert num_edges == 1, f"{node.get_id()} has {num_edges} duplicate {edge_type} edges with {value=}"
