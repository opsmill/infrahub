import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, RelationshipCardinality, RelationshipKind
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m013_convert_git_password_credential import (
    Migration013,
    Migration013AddInternalStatusData,
    Migration013ConvertCoreRepositoryWithCred,
    Migration013ConvertCoreRepositoryWithoutCred,
    Migration013DeleteUsernamePasswordGenericSchema,
)
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot, internal_schema
from infrahub.core.schema_manager import SchemaBranch
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase

GIT_SCHEMA = NodeSchema(
    name="GenericRepository",
    namespace="Core",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        AttributeSchema(
            name="name",
            kind="Text",
            branch=BranchSupportType.AGNOSTIC,
        ),
        AttributeSchema(
            name="description",
            kind="Text",
            branch=BranchSupportType.AGNOSTIC,
            optional=True,
        ),
        AttributeSchema(
            name="username",
            kind="Text",
            branch=BranchSupportType.AGNOSTIC,
            optional=True,
        ),
        AttributeSchema(
            name="password",
            kind="Text",
            branch=BranchSupportType.AGNOSTIC,
            optional=True,
        ),
    ],
)

PASSWORD_CRED = NodeSchema(
    name="PasswordCredential",
    namespace="Core",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        AttributeSchema(
            name="name",
            kind="Text",
            branch=BranchSupportType.AGNOSTIC,
        ),
        AttributeSchema(
            name="label",
            kind="Text",
            branch=BranchSupportType.AGNOSTIC,
        ),
        AttributeSchema(
            name="description",
            kind="Text",
            branch=BranchSupportType.AGNOSTIC,
        ),
        AttributeSchema(
            name="username",
            kind="Text",
            branch=BranchSupportType.AGNOSTIC,
        ),
        AttributeSchema(
            name="password",
            kind="Text",
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
        AttributeSchema(
            name="inherit_from",
            kind="List",
            branch=BranchSupportType.AGNOSTIC,
            optional=True,
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
async def migration_013_data(db: InfrahubDatabase, reset_registry, default_branch, delete_all_nodes_in_db):
    # load the internal schema from
    schema = SchemaRoot(**internal_schema)
    schema_branch = SchemaBranch(cache={}, name="default_branch")
    schema_branch.load_schema(schema=schema)
    schema_branch.process()

    repo1 = await Node.init(db=db, schema=GIT_SCHEMA)
    await repo1.new(db=db, name="repo1 initial", username="user1 initial", password="pwd1 initial")
    await repo1.save(db=db)

    # Update values to ensure the migration will pick the last one
    repo1.name.value = "repo1"
    repo1.username.value = "user1"
    repo1.password.value = "pwd1"
    await repo1.save(db=db)

    repo2 = await Node.init(db=db, schema=GIT_SCHEMA)
    await repo2.new(db=db, name="repo2", username="user2", password="pwd2")
    await repo2.save(db=db)

    repo3 = await Node.init(db=db, schema=GIT_SCHEMA)
    await repo3.new(db=db, name="repo3", description="no-cred")
    await repo3.save(db=db)


@pytest.fixture
async def migration_013_schema(db: InfrahubDatabase, reset_registry, default_branch, delete_all_nodes_in_db):
    schema = SchemaRoot(**internal_schema)
    schema_branch = SchemaBranch(cache={}, name="default_branch")
    schema_branch.load_schema(schema=schema)
    schema_branch.process()

    node1 = await Node.init(db=db, schema=NODE_SCHEMA)
    await node1.new(db=db, name="GenericRepository", namespace="Core")
    await node1.save(db=db)

    attr1 = await Node.init(db=db, schema=ATTRIBUTE_SCHEMA)
    await attr1.new(db=db, name="name", node=node1)
    await attr1.save(db=db)

    attr2 = await Node.init(db=db, schema=ATTRIBUTE_SCHEMA)
    await attr2.new(db=db, name="username", node=node1)
    await attr2.save(db=db)

    attr3 = await Node.init(db=db, schema=ATTRIBUTE_SCHEMA)
    await attr3.new(db=db, name="password", node=node1)
    await attr3.save(db=db)

    attr4 = await Node.init(db=db, schema=ATTRIBUTE_SCHEMA)
    await attr4.new(db=db, name="donttouch", node=node1)
    await attr4.save(db=db)


async def test_migration_013_query_01(
    db: InfrahubDatabase, reset_registry, default_branch, delete_all_nodes_in_db, migration_013_data
):
    registry.branch[default_branch.name] = default_branch
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

    schema_branch.set(name=PASSWORD_CRED.kind, schema=PASSWORD_CRED)

    # nbr_nodes_before = await count_nodes(db=db, label="CoreAccount")
    nbr_rels_before = await count_relationships(db=db)

    query = await Migration013ConvertCoreRepositoryWithCred.init(db=db)
    await query.execute(db=db)
    assert query.stats.get_counter(name="nodes_created") == 6 * 2

    nbr_rels_after = await count_relationships(db=db)
    assert nbr_rels_after == nbr_rels_before + (19 * 2)

    creds = await NodeManager.query(db=db, schema=PASSWORD_CRED, branch=default_branch)

    assert len(creds) == 2
    creds_by_name = {cred.name.value: cred for cred in creds}
    assert creds_by_name["repo1"].description.value == "Credential for repo1"
    assert creds_by_name["repo1"].label.value == "repo1"
    assert creds_by_name["repo1"].username.value == "user1"
    assert creds_by_name["repo1"].password.value == "pwd1"

    # Execute the same query one more time to validate that it doesn't do anything
    query = await Migration013ConvertCoreRepositoryWithCred.init(db=db)
    await query.execute(db=db)
    assert query.stats.get_counter(name="nodes_created") == 0

    nbr_rels_after2 = await count_relationships(db=db)
    assert nbr_rels_after == nbr_rels_after2


async def test_migration_013_query_02(
    db: InfrahubDatabase, reset_registry, default_branch, delete_all_nodes_in_db, migration_013_data
):
    registry.branch[default_branch.name] = default_branch
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

    schema_branch.set(name=PASSWORD_CRED.kind, schema=PASSWORD_CRED)

    # nbr_nodes_before = await count_nodes(db=db, label="CoreAccount")
    nbr_rels_before = await count_relationships(db=db)

    query = await Migration013ConvertCoreRepositoryWithoutCred.init(db=db)
    await query.execute(db=db)

    nbr_rels_after = await count_relationships(db=db)
    assert nbr_rels_after == nbr_rels_before + 2

    creds = await NodeManager.query(db=db, schema=PASSWORD_CRED, branch=default_branch)
    assert len(creds) == 0

    # Execute the same query one more time to validate that it doesn't do anything
    query = await Migration013ConvertCoreRepositoryWithoutCred.init(db=db)
    await query.execute(db=db)

    nbr_rels_after2 = await count_relationships(db=db)
    assert nbr_rels_after == nbr_rels_after2


async def test_migration_013_delete_username_password_schema(
    db: InfrahubDatabase, reset_registry, default_branch, delete_all_nodes_in_db, migration_013_schema
):
    nbr_rels_before = await count_relationships(db=db)

    query = await Migration013DeleteUsernamePasswordGenericSchema.init(db=db)
    await query.execute(db=db)

    query = await Migration013DeleteUsernamePasswordGenericSchema.init(db=db)
    await query.execute(db=db)

    nbr_rels_after = await count_relationships(db=db)

    assert nbr_rels_after == nbr_rels_before + (2 * 3)


async def test_migration_013_add_internal_status_data(
    db: InfrahubDatabase, reset_registry, default_branch, delete_all_nodes_in_db, migration_013_data
):
    nbr_rels_before = await count_relationships(db=db)

    query = await Migration013AddInternalStatusData.init(db=db)
    await query.execute(db=db)
    assert query.stats.get_counter(name="nodes_created") == 3 + 1

    query = await Migration013AddInternalStatusData.init(db=db)
    await query.execute(db=db)
    assert query.stats.get_counter(name="nodes_created") == 0

    nbr_rels_after = await count_relationships(db=db)

    assert nbr_rels_after == nbr_rels_before + (3 * 4)


async def test_migration_013(
    db: InfrahubDatabase,
    reset_registry,
    default_branch,
    delete_all_nodes_in_db,
    migration_013_data,
    migration_013_schema,
):
    nbr_rels_before = await count_relationships(db=db)
    nbr_nodes_before = await count_nodes(db=db)

    migration = Migration013()
    execution_result = await migration.execute(db=db)
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors

    nbr_rels_after = await count_relationships(db=db)
    nbr_nodes_after = await count_nodes(db=db)

    assert nbr_nodes_after == nbr_nodes_before + (6 * 2) + (3 + 1)
    assert nbr_rels_after == nbr_rels_before + (19 * 2) + (2 * 3) + (3 * 4) + 2
