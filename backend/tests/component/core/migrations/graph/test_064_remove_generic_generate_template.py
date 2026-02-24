import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.graph.m064_remove_generic_generate_template import Migration064
from infrahub.core.migrations.schema.node_attribute_add import NodeAttributeAddMigration
from infrahub.core.migrations.shared import InternalSchemaMigration, MigrationInput
from infrahub.core.path import SchemaPath
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

COUNT_GENERATE_TEMPLATE_ON_GENERICS = """
MATCH (sg:SchemaGeneric)-[r:HAS_ATTRIBUTE]->(attr:Attribute {name: "generate_template"})
WHERE r.status = "active" AND r.to IS NULL
RETURN count(attr) AS count
"""

COUNT_GENERATE_TEMPLATE_SCHEMA_ATTRIBUTE = """
MATCH p1 = (sn:SchemaNode)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})
    -[:HAS_VALUE]->(:AttributeValueIndexed {value: "Generic"})
WHERE all(r IN relationships(p1) WHERE r.status = "active" AND r.to IS NULL)
MATCH p2 = (sn)-[:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})
    -[:HAS_VALUE]->(:AttributeValueIndexed {value: "Schema"})
WHERE all(r IN relationships(p2) WHERE r.status = "active" AND r.to IS NULL)
WITH sn
LIMIT 1
MATCH p3 = (sn)-[:IS_RELATED]-(:Relationship {name: "schema__node__attributes"})
    -[:IS_RELATED]-(sa:SchemaAttribute)
    -[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})
    -[:HAS_VALUE]->(:AttributeValueIndexed {value: "generate_template"})
WHERE all(r IN relationships(p3) WHERE r.status = "active" AND r.to IS NULL)
RETURN count(sa) AS count
"""


@pytest.fixture
async def migration_062_data(
    db: InfrahubDatabase, reset_registry: None, default_branch: Branch, register_core_schema_db: None
) -> None:
    """Add generate_template attribute to SchemaGeneric nodes, simulating the old DB state."""
    internal_schema_branch = InternalSchemaMigration.get_internal_schema()
    schema_node = internal_schema_branch.get_node(name="SchemaNode")
    schema_generic = internal_schema_branch.get_node(name="SchemaGeneric")

    # Build a SchemaGeneric definition that includes generate_template
    schema_generic_with_attr = internal_schema_branch.get_node(name="SchemaGeneric")
    generate_template_attr = schema_node.get_attribute(name="generate_template")
    schema_generic_with_attr.attributes.append(generate_template_attr)

    add_migration = NodeAttributeAddMigration(
        new_node_schema=schema_generic_with_attr,
        previous_node_schema=schema_generic,
        schema_path=SchemaPath(
            schema_kind="SchemaGeneric", path_type=SchemaPathType.ATTRIBUTE, field_name="generate_template"
        ),
    )
    await add_migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

    # Also add generate_template SchemaAttribute to the SchemaGeneric type definition
    # This simulates the old DB state where update_core_schema stored the attribute definition
    schema_generic_def = registry.schema.get(name="SchemaGeneric", branch=default_branch, duplicate=True)
    gt_attr = generate_template_attr.duplicate()
    gt_attr.id = None
    schema_generic_def.attributes.append(gt_attr)
    await registry.schema.update_node_in_db(
        node=schema_generic_def, branch=default_branch, db=db, at=Timestamp(), user_id="migration-test"
    )


async def test_migration_062(
    db: InfrahubDatabase, reset_registry: None, default_branch: Branch, migration_062_data: None
) -> None:
    result_before = await db.execute_query(query=COUNT_GENERATE_TEMPLATE_ON_GENERICS)
    assert result_before[0].get("count") > 0

    schema_attr_before = await db.execute_query(query=COUNT_GENERATE_TEMPLATE_SCHEMA_ATTRIBUTE)
    assert schema_attr_before[0].get("count") > 0

    migration = Migration064.init()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors

    result_after = await db.execute_query(query=COUNT_GENERATE_TEMPLATE_ON_GENERICS)
    assert result_after[0].get("count") == 0

    schema_attr_after = await db.execute_query(query=COUNT_GENERATE_TEMPLATE_SCHEMA_ATTRIBUTE)
    assert schema_attr_after[0].get("count") == 0
