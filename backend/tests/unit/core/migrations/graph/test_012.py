import pytest

from infrahub.core.constants import BranchSupportType, RelationshipCardinality, RelationshipKind
from infrahub.core.migrations.graph.m012_convert_account_generic import (
    Migration012,
    Migration012AddLabel,
    Migration012RenameTypeAttributeData,
    Migration012RenameTypeAttributeSchema,
)
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot, internal_schema
from infrahub.core.schema_manager import SchemaBranch
from infrahub.core.utils import count_nodes
from infrahub.database import InfrahubDatabase

ACCOUNT_SCHEMA = NodeSchema(
    name="Account",
    namespace="Core",
    label="Account",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        AttributeSchema(
            name="name",
            kind="Text",
            label="Name",
            branch=BranchSupportType.AGNOSTIC,
        ),
        AttributeSchema(
            name="type",
            kind="Text",
            label="Name",
            enum=["User", "Script", "Bot", "Git"],
            branch=BranchSupportType.AGNOSTIC,
        ),
    ],
)

NODE_SCHEMA = NodeSchema(
    name="Node",
    namespace="Schema",
    branch=BranchSupportType.AWARE,
    attributes=[
        AttributeSchema(
            name="name",
            kind="Text",
            branch=BranchSupportType.AWARE,
        ),
        AttributeSchema(
            name="namespace",
            kind="Text",
            branch=BranchSupportType.AWARE,
        ),
    ],
    relationships=[
        RelationshipSchema(
            name="attributes",
            peer="SchemaAttribute",
            kind=RelationshipKind.COMPONENT,
            identifier="schema__node__attributes",
            cardinality=RelationshipCardinality.MANY,
            branch=BranchSupportType.AWARE.value,
            optional=True,
        ),
    ],
)

ATTRIBUTE_SCHEMA = NodeSchema(
    name="Attribute",
    namespace="Schema",
    branch=BranchSupportType.AWARE,
    attributes=[
        AttributeSchema(
            name="name",
            kind="Text",
            branch=BranchSupportType.AWARE,
        ),
    ],
    relationships=[
        RelationshipSchema(
            name="node",
            peer="SchemaNode",
            kind=RelationshipKind.PARENT,
            identifier="schema__node__attributes",
            cardinality=RelationshipCardinality.ONE,
            branch=BranchSupportType.AWARE.value,
            optional=False,
        )
    ],
)


@pytest.fixture
async def migration_012_data(db: InfrahubDatabase, reset_registry, default_branch, delete_all_nodes_in_db):
    #     # load the internal schema from
    schema = SchemaRoot(**internal_schema)
    schema_branch = SchemaBranch(cache={}, name="default_branch")
    schema_branch.load_schema(schema=schema)
    schema_branch.process()

    node1 = await Node.init(db=db, schema=ACCOUNT_SCHEMA)
    await node1.new(db=db, name="User1", type="User")
    await node1.save(db=db)

    node2 = await Node.init(db=db, schema=ACCOUNT_SCHEMA)
    await node2.new(db=db, name="Script2", type="Script")
    await node2.save(db=db)


@pytest.fixture
async def migration_012_schema(db: InfrahubDatabase, reset_registry, default_branch, delete_all_nodes_in_db):
    schema = SchemaRoot(**internal_schema)
    schema_branch = SchemaBranch(cache={}, name="default_branch")
    schema_branch.load_schema(schema=schema)
    schema_branch.process()

    node1 = await Node.init(db=db, schema=NODE_SCHEMA)
    await node1.new(db=db, name="Account", namespace="Core")
    await node1.save(db=db)

    node2 = await Node.init(db=db, schema=ATTRIBUTE_SCHEMA)
    await node2.new(db=db, name="type", node=node1)
    await node2.save(db=db)


async def test_migration_012_add_label(
    db: InfrahubDatabase, reset_registry, default_branch, delete_all_nodes_in_db, migration_012_data
):
    nbr_nodes_before = await count_nodes(db=db, label="CoreAccount")

    query = await Migration012AddLabel.init(db=db)
    await query.execute(db=db)
    assert query.stats.get_counter(name="nodes_created") == 2

    query = await Migration012AddLabel.init(db=db)
    await query.execute(db=db)
    assert query.stats.get_counter(name="nodes_created") == 0

    nbr_nodes_after = await count_nodes(db=db, label="CoreAccount")
    assert nbr_nodes_after == nbr_nodes_before + 2


async def test_migration_012_rename_type_data(
    db: InfrahubDatabase, reset_registry, default_branch, delete_all_nodes_in_db, migration_012_data
):
    nbr_attrs_before = await count_nodes(db=db, label="Attribute")

    query = await Migration012RenameTypeAttributeData.init(db=db)
    await query.execute(db=db)
    assert query.stats.get_counter(name="nodes_created") == 2

    query = await Migration012RenameTypeAttributeData.init(db=db)
    await query.execute(db=db)
    assert query.stats.get_counter(name="nodes_created") == 0

    nbr_attrs_after = await count_nodes(db=db, label="Attribute")
    assert nbr_attrs_after == nbr_attrs_before + 2


async def test_migration_012_rename_type_schema(
    db: InfrahubDatabase, reset_registry, default_branch, delete_all_nodes_in_db, migration_012_schema
):
    nbr_attrs_value_before = await count_nodes(db=db, label="AttributeValue")

    query = await Migration012RenameTypeAttributeSchema.init(db=db)
    await query.execute(db=db)

    query = await Migration012RenameTypeAttributeSchema.init(db=db)
    await query.execute(db=db)

    nbr_attrs_value_after = await count_nodes(db=db, label="AttributeValue")
    assert nbr_attrs_value_after == nbr_attrs_value_before + 1


async def test_migration_012(
    db: InfrahubDatabase, reset_registry, default_branch, delete_all_nodes_in_db, migration_012_data
):
    nbr_nodes_before = await count_nodes(db=db, label="CoreAccount")
    nbr_attrs_before = await count_nodes(db=db, label="Attribute")

    migration = Migration012()
    execution_result = await migration.execute(db=db)
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors

    nbr_nodes_after = await count_nodes(db=db, label="CoreAccount")
    nbr_attrs_after = await count_nodes(db=db, label="Attribute")

    assert nbr_nodes_after == nbr_nodes_before + 2
    assert nbr_attrs_after == nbr_attrs_before + 2
