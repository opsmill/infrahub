import pytest

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m058_remove_profiles_schema_relationships import Migration058
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase

BREAK_PARENT_LINK = """
MATCH (:SchemaRelationship {uuid: $sr_uuid})-[:IS_RELATED]-(rel:Relationship {name: "schema__node__relationships"})
DETACH DELETE rel
"""


@pytest.fixture
async def migration_058_data(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    register_internal_models_schema: SchemaBranch,
) -> dict[str, Node]:
    # Create parent schemas
    node_schema = await Node.init(db=db, branch=default_branch, schema="SchemaNode")
    await node_schema.new(db=db, name="TestNode", namespace="Test")
    await node_schema.save(db=db)

    generic_schema = await Node.init(db=db, branch=default_branch, schema="SchemaGeneric")
    await generic_schema.new(db=db, name="TestGeneric", namespace="Test")
    await generic_schema.save(db=db)

    # Create "profiles" SchemaRelationship instances linked to parent schemas
    profiles_rel_node = await Node.init(db=db, branch=default_branch, schema="SchemaRelationship")
    await profiles_rel_node.new(db=db, name="profiles", peer="TestProfile", node=node_schema)
    await profiles_rel_node.save(db=db)

    profiles_rel_generic = await Node.init(db=db, branch=default_branch, schema="SchemaRelationship")
    await profiles_rel_generic.new(db=db, name="profiles", peer="TestProfile", node=generic_schema)
    await profiles_rel_generic.save(db=db)

    # Create "object_template" SchemaRelationship instances linked to parent schemas
    obj_template_rel_node = await Node.init(db=db, branch=default_branch, schema="SchemaRelationship")
    await obj_template_rel_node.new(db=db, name="object_template", peer="TestTemplate", node=node_schema)
    await obj_template_rel_node.save(db=db)

    obj_template_rel_generic = await Node.init(db=db, branch=default_branch, schema="SchemaRelationship")
    await obj_template_rel_generic.new(db=db, name="object_template", peer="TestTemplate", node=generic_schema)
    await obj_template_rel_generic.save(db=db)

    # Create a normal SchemaRelationship that should NOT be deleted by any query
    keeper_rel = await Node.init(db=db, branch=default_branch, schema="SchemaRelationship")
    await keeper_rel.new(db=db, name="some_real_rel", peer="TestPeer", node=node_schema)
    await keeper_rel.save(db=db)

    # Create an orphaned SchemaRelationship (create normally, then break parent link)
    orphan_rel = await Node.init(db=db, branch=default_branch, schema="SchemaRelationship")
    await orphan_rel.new(db=db, name="orphan_rel", peer="TestPeer", node=node_schema)
    await orphan_rel.save(db=db)

    # Break the parent link to simulate an orphaned state
    # custom cypher is required b/c the relationship is required, but this state can exist in a live Infrahub system
    await db.execute_query(query=BREAK_PARENT_LINK, params={"sr_uuid": orphan_rel.id})

    return {
        "node_schema": node_schema,
        "generic_schema": generic_schema,
        "profiles_rel_node": profiles_rel_node,
        "profiles_rel_generic": profiles_rel_generic,
        "obj_template_rel_node": obj_template_rel_node,
        "obj_template_rel_generic": obj_template_rel_generic,
        "keeper_rel": keeper_rel,
        "orphan_rel": orphan_rel,
    }


async def test_migration_058(
    db: InfrahubDatabase,
    default_branch: Branch,
    migration_058_data: dict[str, Node],
) -> None:
    # Verify pre-migration state
    profiles_count = await NodeManager.count(db=db, schema="SchemaRelationship", filters={"name__value": "profiles"})
    assert profiles_count == 2
    obj_template_count = await NodeManager.count(
        db=db, schema="SchemaRelationship", filters={"name__value": "object_template"}
    )
    assert obj_template_count == 2
    orphan_count = await NodeManager.count(db=db, schema="SchemaRelationship", filters={"name__value": "orphan_rel"})
    assert orphan_count == 1

    # Run the full migration
    migration = Migration058()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors

    # Verify all "profiles" SchemaRelationship nodes are deleted
    profiles_count = await NodeManager.count(db=db, schema="SchemaRelationship", filters={"name__value": "profiles"})
    assert profiles_count == 0

    # Verify all "object_template" SchemaRelationship nodes are deleted
    obj_template_count = await NodeManager.count(
        db=db, schema="SchemaRelationship", filters={"name__value": "object_template"}
    )
    assert obj_template_count == 0

    # Verify the orphaned SchemaRelationship is deleted
    orphan = await NodeManager.get_one(db=db, branch=default_branch, id=migration_058_data["orphan_rel"].id)
    assert orphan is None

    # Verify the normal SchemaRelationship is NOT deleted
    keeper = await NodeManager.get_one(db=db, branch=default_branch, id=migration_058_data["keeper_rel"].id)
    assert keeper is not None
