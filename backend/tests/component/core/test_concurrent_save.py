import asyncio

import pytest

from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase, get_db


class TestNodeConcurrentSave:
    the_value = 122

    @pytest.fixture
    async def node_with_duplicate_edges(self, db: InfrahubDatabase, car_person_schema: SchemaBranch) -> Node:
        # create a node
        node = await Node.init(db=db, schema="TestPerson")
        await node.new(db=db, name="Concurrynthia")
        await node.save(db=db)

        # make an update
        node.height.value = self.the_value

        # save the update simulataneously on two different db connections
        # creating multiple AttributeValue nodes with the same value
        db_drivers: list[InfrahubDatabase] = []
        try:
            for _ in range(2):
                driver = InfrahubDatabase(driver=await get_db(retry=5))
                db_drivers.append(driver)

            await asyncio.gather(*[node.save(db=db_drivers[i]) for i in range(2)])
        finally:
            for driver in db_drivers:
                await driver.close()
        return node

    async def _validate_no_duplicate_edges(self, db: InfrahubDatabase, node: Node, attribute_name: str) -> None:
        # validate that this node
        #  - does not have duplicate HAS_VALUE or IS_PROTECTED edges
        #  - only connects to one AttributeValue node even though multiple exist
        params = {"node_id": node.get_id(), "attribute_name": attribute_name}
        query = """
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
        MATCH (a)-[e]-(p)
        RETURN a, type(e) AS edge_type, p.value AS value, COUNT(*) AS num_edges
        """
        results = await db.execute_query(query=query, params=params)
        for result in results:
            edge_type = result.get("edge_type")
            value = result.get("value")
            num_edges = result.get("num_edges")
            assert num_edges == 1, f"{num_edges} duplicate {edge_type} edges with {value=}"

    async def test_new_node_avoids_duplicate_edges(
        self, db: InfrahubDatabase, car_person_schema: SchemaBranch, node_with_duplicate_edges: Node
    ) -> None:
        another_node = await Node.init(db=db, schema="TestPerson")
        await another_node.new(db=db, name="Tango", height=self.the_value)
        await another_node.save(db=db)

        await self._validate_no_duplicate_edges(db=db, node=another_node, attribute_name="height")

    async def test_updated_node_avoids_duplicate_edges(
        self, db: InfrahubDatabase, car_person_schema: SchemaBranch, node_with_duplicate_edges: Node
    ) -> None:
        another_node = await Node.init(db=db, schema="TestPerson")
        await another_node.new(db=db, name="Cash", height=self.the_value - 1)
        await another_node.save(db=db)

        another_node.height.value = self.the_value
        await another_node.save(db=db)

        await self._validate_no_duplicate_edges(db=db, node=another_node, attribute_name="height")
