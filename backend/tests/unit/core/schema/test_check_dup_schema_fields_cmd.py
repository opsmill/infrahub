import pytest

from infrahub.cli.db_commands.clean_duplicate_schema_fields import clean_duplicate_schema_fields
from infrahub.core.branch.models import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


async def merge_nodes(
    db: InfrahubDatabase, node_uuids: list[str], source_branch_name: str, target_branch_name: str, at: Timestamp
) -> None:
    """
    Do a simplified graph merge of any active edges for particular Nodes on a source branch into a target branch.
    """
    query = """
MATCH (n:Node)
WHERE n.uuid IN $node_uuids

MATCH (n)-[r:IS_PART_OF {branch: $source_branch_name, status: "active"}]->(root)
CREATE (n)-[new_r:IS_PART_OF]->(root)
SET new_r = properties(r)
SET new_r.branch = $target_branch_name
SET new_r.from = $at

WITH DISTINCT n
MATCH (n)-[r:HAS_ATTRIBUTE|IS_RELATED {branch: $source_branch_name, status: "active"}]-(attr_or_rel:Attribute|Relationship)
WITH DISTINCT n, attr_or_rel
CALL (attr_or_rel) {
    MATCH (attr_or_rel)-[r {branch: $source_branch_name, status: "active"}]->(peer)
    WITH *, type(r) AS edge_type
    CREATE (attr_or_rel)-[new_r:$(edge_type)]->(peer)
    SET new_r = properties(r)
    SET new_r.branch = $target_branch_name
    SET new_r.from = $at
}
CALL (attr_or_rel) {
    MATCH (attr_or_rel)<-[r {branch: $source_branch_name, status: "active"}]-(peer)
    WITH *, type(r) AS edge_type
    CREATE (attr_or_rel)<-[new_r:$(edge_type)]-(peer)
    SET new_r = properties(r)
    SET new_r.branch = $target_branch_name
    SET new_r.from = $at
}
    """
    params = {
        "node_uuids": node_uuids,
        "source_branch_name": source_branch_name,
        "target_branch_name": target_branch_name,
        "at": at.to_string(),
    }
    await db.execute_query(query=query, params=params)


class TestCheckDuplicateSchemaFields:
    @pytest.fixture
    async def load_main_schema(
        self, db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema: SchemaBranch
    ) -> dict[str, Node]:
        node_schema = await Node.init(db=db, branch=default_branch, schema="SchemaNode")
        await node_schema.new(db=db, name="Schema", namespace="Test")
        await node_schema.save(db=db)

        generic_schema = await Node.init(db=db, branch=default_branch, schema="SchemaGeneric")
        await generic_schema.new(db=db, name="Generic", namespace="Test")
        await generic_schema.save(db=db)

        attribute_schema_1 = await Node.init(db=db, branch=default_branch, schema="SchemaAttribute")
        await attribute_schema_1.new(db=db, name="attribute_1", kind="Text", node=node_schema)
        await attribute_schema_1.save(db=db)

        generic_attribute_schema_1 = await Node.init(db=db, branch=default_branch, schema="SchemaAttribute")
        await generic_attribute_schema_1.new(db=db, name="attribute_1", kind="Text", node=generic_schema)
        await generic_attribute_schema_1.save(db=db)

        relationship_schema_1 = await Node.init(db=db, branch=default_branch, schema="SchemaRelationship")
        await relationship_schema_1.new(db=db, name="relationship_1", peer="SomeThing", node=node_schema)
        await relationship_schema_1.save(db=db)

        generic_relationship_schema_1 = await Node.init(db=db, branch=default_branch, schema="SchemaRelationship")
        await generic_relationship_schema_1.new(db=db, name="relationship_1", peer="SomeThing", node=generic_schema)
        await generic_relationship_schema_1.save(db=db)

        return {
            "node_schema": node_schema,
            "attribute_schema_1": attribute_schema_1,
            "relationship_schema_1": relationship_schema_1,
            "generic_schema": generic_schema,
            "generic_attribute_schema_1": generic_attribute_schema_1,
            "generic_relationship_schema_1": generic_relationship_schema_1,
        }

    @pytest.fixture
    async def branch(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name="branch_1")

    @pytest.fixture
    async def load_broken_schema(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        load_main_schema: dict[str, Node],
        branch: Branch,
    ):
        node_schema = load_main_schema["node_schema"]
        generic_schema = load_main_schema["generic_schema"]

        attribute_schema_2_branch = await Node.init(db=db, branch=branch, schema="SchemaAttribute")
        await attribute_schema_2_branch.new(db=db, name="attribute_2", kind="Text", node=node_schema)
        await attribute_schema_2_branch.save(db=db)

        attribute_schema_2_main = await Node.init(db=db, branch=default_branch, schema="SchemaAttribute")
        await attribute_schema_2_main.new(db=db, name="attribute_2", kind="Text", node=node_schema)
        await attribute_schema_2_main.save(db=db)

        generic_attribute_schema_2_branch = await Node.init(db=db, branch=branch, schema="SchemaAttribute")
        await generic_attribute_schema_2_branch.new(db=db, name="attribute_2", kind="Text", node=generic_schema)
        await generic_attribute_schema_2_branch.save(db=db)

        generic_attribute_schema_2_main = await Node.init(db=db, branch=default_branch, schema="SchemaAttribute")
        await generic_attribute_schema_2_main.new(db=db, name="attribute_2", kind="Text", node=generic_schema)
        await generic_attribute_schema_2_main.save(db=db)

        relationship_schema_2_branch = await Node.init(db=db, branch=branch, schema="SchemaRelationship")
        await relationship_schema_2_branch.new(db=db, name="relationship_2", peer="SomeThing", node=node_schema)
        await relationship_schema_2_branch.save(db=db)

        relationship_schema_2_main = await Node.init(db=db, branch=default_branch, schema="SchemaRelationship")
        await relationship_schema_2_main.new(db=db, name="relationship_2", peer="SomeThing", node=node_schema)
        await relationship_schema_2_main.save(db=db)

        generic_relationship_schema_2_branch = await Node.init(db=db, branch=branch, schema="SchemaRelationship")
        await generic_relationship_schema_2_branch.new(
            db=db, name="relationship_2", peer="SomeThing", node=generic_schema
        )
        await generic_relationship_schema_2_branch.save(db=db)

        generic_relationship_schema_2_main = await Node.init(db=db, branch=default_branch, schema="SchemaRelationship")
        await generic_relationship_schema_2_main.new(
            db=db, name="relationship_2", peer="SomeThing", node=generic_schema
        )
        await generic_relationship_schema_2_main.save(db=db)

        return {
            "attribute_schema_2_branch": attribute_schema_2_branch,
            "attribute_schema_2_main": attribute_schema_2_main,
            "relationship_schema_2_branch": relationship_schema_2_branch,
            "relationship_schema_2_main": relationship_schema_2_main,
            "generic_attribute_schema_2_branch": generic_attribute_schema_2_branch,
            "generic_attribute_schema_2_main": generic_attribute_schema_2_main,
            "generic_relationship_schema_2_branch": generic_relationship_schema_2_branch,
            "generic_relationship_schema_2_main": generic_relationship_schema_2_main,
        }

    async def test_schema_with_duplicate_fields(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        load_main_schema: dict[str, Node],
        load_broken_schema: dict[str, Node],
        branch: Branch,
    ) -> None:
        node_schema_id = load_main_schema["node_schema"].id
        attr_schema_1_main_id = load_main_schema["attribute_schema_1"].id
        attr_schema_2_branch_id = load_broken_schema["attribute_schema_2_branch"].id
        attr_schema_2_main_id = load_broken_schema["attribute_schema_2_main"].id
        relationship_schema_1_main_id = load_main_schema["relationship_schema_1"].id
        relationship_schema_2_branch_id = load_broken_schema["relationship_schema_2_branch"].id
        relationship_schema_2_main_id = load_broken_schema["relationship_schema_2_main"].id
        generic_schema_id = load_main_schema["generic_schema"].id
        generic_attr_schema_1_main_id = load_main_schema["generic_attribute_schema_1"].id
        generic_attr_schema_2_branch_id = load_broken_schema["generic_attribute_schema_2_branch"].id
        generic_attr_schema_2_main_id = load_broken_schema["generic_attribute_schema_2_main"].id
        generic_relationship_schema_1_main_id = load_main_schema["generic_relationship_schema_1"].id
        generic_relationship_schema_2_branch_id = load_broken_schema["generic_relationship_schema_2_branch"].id
        generic_relationship_schema_2_main_id = load_broken_schema["generic_relationship_schema_2_main"].id
        await merge_nodes(
            db=db,
            node_uuids=[
                attr_schema_2_branch_id,
                relationship_schema_2_branch_id,
                generic_attr_schema_2_branch_id,
                generic_relationship_schema_2_branch_id,
            ],
            source_branch_name=branch.name,
            target_branch_name=default_branch.name,
            at=Timestamp(),
        )

        await clean_duplicate_schema_fields(db=db, fix=True)

        # verify that attribute_schema_1 is still present on main
        attr_schema_1_main = await NodeManager.get_one(db=db, branch=default_branch, id=attr_schema_1_main_id)
        assert attr_schema_1_main is not None
        # verify attribute_schema_2 is present on main and on the branch
        attr_schema_2_branch = await NodeManager.get_one(db=db, branch=default_branch, id=attr_schema_2_branch_id)
        assert attr_schema_2_branch is not None
        attr_schema_2_main = await NodeManager.get_one(db=db, branch=branch, id=attr_schema_2_branch_id)
        assert attr_schema_2_main is not None
        # validate that the earlier version of the duplicated AttributeSchema is removed
        # on main, the earlier version is attribute_schema_2_main b/c the merge happened after
        deduplicated = await NodeManager.get_one(db=db, branch=default_branch, id=attr_schema_2_main_id)
        assert deduplicated is None

        # verify that relationship_schema_1 is still present on main
        relationship_schema_1_main = await NodeManager.get_one(
            db=db, branch=default_branch, id=relationship_schema_1_main_id
        )
        assert relationship_schema_1_main is not None
        # verify attribute_schema_2 is present on main and on the branch
        relationship_schema_2_branch = await NodeManager.get_one(
            db=db, branch=default_branch, id=relationship_schema_2_branch_id
        )
        assert relationship_schema_2_branch is not None
        relationship_schema_2_main = await NodeManager.get_one(db=db, branch=branch, id=relationship_schema_2_branch_id)
        assert relationship_schema_2_main is not None
        # validate that the earlier version of the duplicated RelationshipSchema is removed
        deduplicated = await NodeManager.get_one(db=db, branch=default_branch, id=relationship_schema_2_main_id)
        assert deduplicated is None

        # check NodeSchema attributes and relationships relationships
        node_schema = await NodeManager.get_one(db=db, branch=default_branch, id=node_schema_id)
        attributes_rel = await node_schema.attributes.get_relationships(db=db)
        assert len(attributes_rel) == 2
        assert {r.get_peer_id() for r in attributes_rel} == {attr_schema_1_main_id, attr_schema_2_branch_id}
        relationships_rel = await node_schema.relationships.get_relationships(db=db)
        assert len(relationships_rel) == 2
        assert {r.get_peer_id() for r in relationships_rel} == {
            relationship_schema_1_main_id,
            relationship_schema_2_branch_id,
        }

        # verify that attribute_schema_1 is still present on main
        attr_schema_1_main = await NodeManager.get_one(db=db, branch=default_branch, id=generic_attr_schema_1_main_id)
        assert attr_schema_1_main is not None
        # verify attribute_schema_2 is present on main and on the branch
        attr_schema_2_branch = await NodeManager.get_one(
            db=db, branch=default_branch, id=generic_attr_schema_2_branch_id
        )
        assert attr_schema_2_branch is not None
        attr_schema_2_main = await NodeManager.get_one(db=db, branch=branch, id=generic_attr_schema_2_branch_id)
        assert attr_schema_2_main is not None
        # validate that the earlier version of the duplicated AttributeSchema is removed
        # on main, the earlier version is attribute_schema_2_main b/c the merge happened after
        deduplicated = await NodeManager.get_one(db=db, branch=default_branch, id=generic_attr_schema_2_main_id)
        assert deduplicated is None

        # verify that relationship_schema_1 is still present on main
        relationship_schema_1_main = await NodeManager.get_one(
            db=db, branch=default_branch, id=generic_relationship_schema_1_main_id
        )
        assert relationship_schema_1_main is not None
        # verify attribute_schema_2 is present on main and on the branch
        relationship_schema_2_branch = await NodeManager.get_one(
            db=db, branch=default_branch, id=generic_relationship_schema_2_branch_id
        )
        assert relationship_schema_2_branch is not None
        relationship_schema_2_main = await NodeManager.get_one(
            db=db, branch=branch, id=generic_relationship_schema_2_branch_id
        )
        assert relationship_schema_2_main is not None
        # validate that the earlier version of the duplicated RelationshipSchema is removed
        deduplicated = await NodeManager.get_one(db=db, branch=default_branch, id=generic_relationship_schema_2_main_id)
        assert deduplicated is None

        # check NodeSchema attributes and relationships relationships
        generic_schema = await NodeManager.get_one(db=db, branch=default_branch, id=generic_schema_id)
        attributes_rel = await generic_schema.attributes.get_relationships(db=db)
        assert len(attributes_rel) == 2
        assert {r.get_peer_id() for r in attributes_rel} == {
            generic_attr_schema_1_main_id,
            generic_attr_schema_2_branch_id,
        }
        relationships_rel = await generic_schema.relationships.get_relationships(db=db)
        assert len(relationships_rel) == 2
        assert {r.get_peer_id() for r in relationships_rel} == {
            generic_relationship_schema_1_main_id,
            generic_relationship_schema_2_branch_id,
        }
