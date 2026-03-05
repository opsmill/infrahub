import uuid

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    SYSTEM_USER_ID,
    BranchSupportType,
    HashableModelState,
    InfrahubKind,
    MetadataOptions,
    NumberPoolType,
    SchemaPathType,
)
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.migrations.schema.node_attribute_add import (
    NodeAttributeAddMigration,
    NodeAttributeAddMigrationQuery01,
)
from infrahub.core.migrations.schema.node_attribute_remove import (
    NodeAttributeRemoveMigration,
    NodeAttributeRemoveMigrationQuery01,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.definitions.core.template import core_object_template
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_nodes
from infrahub.database import InfrahubDatabase
from tests.db_snapshot import DbSnapshotter
from tests.helpers.edge_timestamps import assert_edge_timestamps


@pytest.fixture
async def car_person_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> SchemaBranch:
    registry.schema.register_schema(schema=SchemaRoot(generics=[core_object_template]), branch=default_branch.name)
    for node in car_person_schema_unregistered.nodes:
        node.generate_template = True
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


@pytest.fixture
async def schema_aware() -> NodeSchema:
    SCHEMA = {
        "name": "Car",
        "namespace": "Test",
        "branch": "aware",
        "attributes": [
            {"name": "nbr_doors", "kind": "Number", "branch": "aware"},
        ],
    }

    node = NodeSchema(**SCHEMA)
    return node


@pytest.fixture
async def init_database(db: InfrahubDatabase) -> None:
    params = {
        "nodes": [],
        "rel_props": {"branch": "main", "branch_level": "1", "status": "active", "from": Timestamp().to_string()},
    }

    for _ in range(5):
        node_param = {
            "uuid": str(uuid.uuid4()),
            "kind": "TestCar",
            "namespace": "Test",
            "branch_support": "aware",
        }
        params["nodes"].append(node_param)

    query_init_root = """
    MATCH (root:Root)
    FOREACH ( node IN $nodes |
        CREATE (n:Node:TestCar { uuid: node.uuid, kind: node.kind, namespace: node.namespace, branch_support: node.branch_support })
        CREATE (n)-[r:IS_PART_OF $rel_props ]->(root)
    )
    RETURN root
    """ % {}
    await db.execute_query(query=query_init_root, params=params)


async def test_query01(db: InfrahubDatabase, default_branch, init_database, schema_aware) -> None:
    node = schema_aware

    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 0

    migration = NodeAttributeAddMigration(
        new_node_schema=node,
        previous_node_schema=node,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_doors"),
    )
    query = await NodeAttributeAddMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)

    assert query.get_nbr_migrations_executed() == 5
    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 5

    # Re-execute the query once to ensure that it won't recreate the attribute twice
    query = await NodeAttributeAddMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)

    assert query.get_nbr_migrations_executed() == 0
    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 5


async def test_query01_re_add(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)

    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Attribute") == 22

    # ------------------------------------------
    # Delete the attribute Color
    # ------------------------------------------
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get_node(name="TestCar")
    attr = car_schema.get_attribute(name="color")
    attr.state = HashableModelState.ABSENT

    migration_remove = NodeAttributeRemoveMigration(
        previous_node_schema=schema.get_node(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    query = await NodeAttributeRemoveMigrationQuery01.init(db=db, branch=default_branch, migration=migration_remove)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 2

    # ------------------------------------------
    # Add the attribute Color back
    # ------------------------------------------
    migration_add = NodeAttributeAddMigration(
        new_node_schema=schema.get_node(name="TestCar"),
        previous_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    query = await NodeAttributeAddMigrationQuery01.init(db=db, branch=default_branch, migration=migration_add)
    await query.execute(db=db)

    assert query.get_nbr_migrations_executed() == 2

    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Attribute") == 24

    # Re-execute the query once to ensure that it won't recreate the attribute twice
    query = await NodeAttributeAddMigrationQuery01.init(db=db, branch=default_branch, migration=migration_add)
    await query.execute(db=db)

    assert query.get_nbr_migrations_executed() == 0
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Attribute") == 24


async def test_migration(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node, schema_aware
) -> None:
    # Create TemplateTestPerson nodes to use as owners for TemplateTestCar
    template_person1 = await Node.init(db=db, schema="TemplateTestPerson", branch=default_branch)
    await template_person1.new(db=db, template_name="Template Person 1")
    await template_person1.save(db=db)
    template_person2 = await Node.init(db=db, schema="TemplateTestPerson", branch=default_branch)
    await template_person2.new(db=db, template_name="Template Person 2")
    await template_person2.save(db=db)

    # Create 2 TemplateTestCar nodes so migration also covers templates
    template1 = await Node.init(db=db, schema="TemplateTestCar", branch=default_branch)
    await template1.new(db=db, template_name="Template Accord", color="#111111", owner=template_person1)
    await template1.save(db=db)
    template2 = await Node.init(db=db, schema="TemplateTestCar", branch=default_branch)
    await template2.new(db=db, template_name="Template Camry", color="#222222", owner=template_person2)
    await template2.save(db=db)

    node = schema_aware

    # 1. Snapshot before migration
    snapshotter = DbSnapshotter(db)
    before_snapshot = await snapshotter.snapshot()

    # 2. Count nodes before migration
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="TemplateTestCar") == 2
    count_attr_node = await count_nodes(db=db, label="Attribute")

    # 3. Create explicit timestamp
    at = Timestamp()
    at_str = at.to_string()

    # 4. Execute add migration for nbr_doors
    migration = NodeAttributeAddMigration(
        new_node_schema=node,
        previous_node_schema=node,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_doors"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=default_branch)
    assert not execution_result.errors
    # 2 TestCar + 2 TemplateTestCar = 4 migrations
    assert execution_result.nbr_migrations_executed == 4

    # 5. Validate nodes after migration
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="TemplateTestCar") == 2
    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 4

    # 6. Validate edge timestamps
    after_snapshot = await snapshotter.snapshot()
    assert_edge_timestamps(before_snapshot, after_snapshot, at_str)


async def test_migration_metadata(db: InfrahubDatabase, car_accord_main: Node, branch: Branch) -> None:
    """Test that vertex metadata is set correctly when adding an attribute"""
    schema = registry.schema.get_schema_branch(name=branch.name)
    car_schema = schema.get_node(name="TestCar")

    # Remove the color attribute first so we can re-add it
    remove_migration = NodeAttributeRemoveMigration(
        previous_node_schema=car_schema,
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    await remove_migration.execute(migration_input=MigrationInput(db=db, at=Timestamp()), branch=branch)

    test_user_id = "test-metadata-user"
    migration_time = Timestamp()

    migration = NodeAttributeAddMigration(
        new_node_schema=car_schema,
        previous_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    execution_result = await migration.execute(
        migration_input=MigrationInput(db=db, at=migration_time, user_id=test_user_id), branch=branch
    )
    assert not execution_result.errors

    nodes = await NodeManager.get_many(
        db=db,
        ids=[car_accord_main.id],
        branch=branch,
        include_metadata=MetadataQueryOptions(
            node_level=MetadataOptions.USER_TIMESTAMPS,
            attribute_level=MetadataOptions.USER_TIMESTAMPS,
        ),
    )
    node = nodes[car_accord_main.id]
    assert node._get_created_at() < migration_time
    assert node._get_created_by() == SYSTEM_USER_ID
    assert node._get_updated_at() == migration_time
    assert node._get_updated_by() == test_user_id

    # Verify attribute metadata via the Node object
    attr = node.color
    assert attr._get_created_at() == migration_time
    assert attr._get_created_by() == test_user_id
    assert attr._get_updated_at() == migration_time
    assert attr._get_updated_by() == test_user_id


# -----------------------------------------------------------------------------
# NumberPool Attribute Add Tests
# -----------------------------------------------------------------------------


@pytest.fixture
async def server_schema_without_numberpool() -> NodeSchema:
    """Return a TestServer schema without the NumberPool attribute."""
    return NodeSchema(
        name="Server",
        namespace="Test",
        default_filter="name__value",
        branch=BranchSupportType.AWARE,
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True, branch=BranchSupportType.AWARE),
        ],
    )


@pytest.fixture
async def server_schema_with_numberpool() -> NodeSchema:
    """Return a TestServer schema with a NumberPool attribute."""
    return NodeSchema(
        name="Server",
        namespace="Test",
        default_filter="name__value",
        branch=BranchSupportType.AWARE,
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True, branch=BranchSupportType.AWARE),
            AttributeSchema(
                name="rack_unit",
                kind="NumberPool",
                optional=False,
                read_only=True,
                branch=BranchSupportType.AWARE,
                parameters=NumberPoolParameters(start_range=1, end_range=100),
            ),
        ],
    )


@pytest.fixture
async def servers_in_db(
    db: InfrahubDatabase,
    branch: Branch,
    register_core_models_schema: SchemaBranch,
    server_schema_without_numberpool: NodeSchema,
) -> list[Node]:
    """Create test servers without the rack_unit attribute."""
    # Register CoreNumberPool implementation class in registry for get_resource method
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool

    # Register the schema without NumberPool
    schema = SchemaRoot(nodes=[server_schema_without_numberpool])
    registry.schema.register_schema(schema=schema, branch=branch.name)

    servers = []
    for i in range(3):
        server = await Node.init(db=db, schema="TestServer", branch=branch)
        await server.new(db=db, name=f"server-{i}")
        await server.save(db=db)
        servers.append(server)
    return servers


async def test_migration_numberpool_attribute(
    db: InfrahubDatabase,
    branch: Branch,
    server_schema_with_numberpool: NodeSchema,
    servers_in_db: list[Node],
) -> None:
    """Test that adding a NumberPool attribute creates the pool, allocates unique values, and sets the source."""
    # Get the current schema (without NumberPool)
    current_schema = registry.schema.get_node_schema(name="TestServer", branch=branch)

    # Verify initial state
    num_server_objects = await NodeManager.count(db=db, schema="TestServer", branch=branch)
    assert num_server_objects == 3
    initial_pool_count = len(
        await NodeManager.query(
            db=db,
            schema="CoreNumberPool",
            filters={"pool_type__value": NumberPoolType.SCHEMA.value},
            branch_agnostic=True,
        )
    )
    assert initial_pool_count == 0

    # Verify the new schema has parameters
    new_attr = server_schema_with_numberpool.get_attribute(name="rack_unit")
    assert isinstance(new_attr.parameters, NumberPoolParameters)

    # Run the migration
    at = Timestamp()
    migration = NodeAttributeAddMigration(
        previous_node_schema=current_schema,
        new_node_schema=server_schema_with_numberpool,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestServer", field_name="rack_unit"),
    )

    # Register the new schema before executing the migration
    registry.schema.set(name="TestServer", schema=server_schema_with_numberpool, branch=branch.name)
    registry.schema.process_schema_branch(name=branch.name)

    execution_result = await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=branch)
    assert not execution_result.errors

    # Verify a CoreNumberPool was created
    pools = await NodeManager.query(
        db=db,
        schema="CoreNumberPool",
        filters={
            "node__value": "TestServer",
            "node_attribute__value": "rack_unit",
            "pool_type__value": NumberPoolType.SCHEMA.value,
        },
        branch_agnostic=True,
    )
    assert len(pools) == 1
    number_pool = pools[0]

    # Verify pool parameters
    assert number_pool.get_attribute("start_range").value == 1
    assert number_pool.get_attribute("end_range").value == 100

    # Query servers and verify they have unique rack_unit values
    servers_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[s.get_id() for s in servers_in_db], include_metadata=MetadataOptions.SOURCE
    )
    assert len(servers_map) == 3

    rack_unit_values = [server.get_attribute("rack_unit").value for server in servers_map.values()]

    # All values should be assigned (not None)
    assert all(v is not None for v in rack_unit_values), "All servers should have rack_unit values assigned"

    # All values should be unique
    assert len(set(rack_unit_values)) == 3, "All rack_unit values should be unique"

    # All values should be within the pool range
    assert all(1 <= v <= 100 for v in rack_unit_values), "All rack_unit values should be within range 1-100"

    # Verify the source is set to the pool for all servers
    for server in servers_map.values():
        source = await server.get_attribute("rack_unit").get_source(db=db)
        assert source is not None, "rack_unit should have a source set"
        assert source.id == number_pool.id, f"rack_unit source should be the pool {number_pool.id}"
