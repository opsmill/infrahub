import uuid
from copy import deepcopy
from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.attribute import BaseAttribute
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    GLOBAL_BRANCH_NAME,
    BranchSupportType,
    HashableModelState,
    InfrahubKind,
    MetadataOptions,
    NumberPoolType,
    SchemaPathType,
)
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
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
from infrahub.core.query.rollback import RollbackScope
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.definitions.core.template import core_object_template
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_nodes
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_graph
from tests.component.core.migrations.schema.metadata_helpers import (
    VertexMetadata,
    branch_edge_fingerprint,
    branch_metadata_fingerprint,
    get_attribute_vertex_metadata,
    get_node_vertex_metadata,
)
from tests.component.core.node.test_branch_agnostic_edges import assert_no_global_edges_with_wrong_branch_level
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

    return NodeSchema(**SCHEMA)


@pytest.fixture
async def schema_aware_inherited() -> NodeSchema:
    SCHEMA = {
        "name": "Car",
        "namespace": "Test",
        "branch": "aware",
        "attributes": [
            {"name": "nbr_doors", "kind": "Number", "branch": "aware", "inherited": True},
        ],
    }

    return NodeSchema(**SCHEMA)


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


async def test_query01(
    db: InfrahubDatabase, default_branch: Branch, init_database: None, schema_aware: NodeSchema
) -> None:
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


async def test_query01_re_add(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
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
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node, schema_aware: NodeSchema
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


MIGRATION_USER_ID = "migration_user"


@dataclass
class _AttributeAdd:
    """State captured around a single ``color`` attribute-add migration on one branch."""

    branch: Branch
    node_id: str
    migration_time: Timestamp
    user_id: str
    node_before: VertexMetadata
    pre_migration_fingerprint: list[tuple]
    pre_migration_metadata: list[tuple]


async def _run_attribute_add_migration(db: InfrahubDatabase, branch: Branch, node_uuid: str) -> _AttributeAdd:
    """Add a brand-new ``doors`` attribute on ``branch``."""
    node_before = await get_node_vertex_metadata(db=db, node_uuid=node_uuid)
    pre_migration_fingerprint = await branch_edge_fingerprint(db=db, branch_name=branch.name)
    pre_migration_metadata = await branch_metadata_fingerprint(db=db, branch_name=branch.name)

    user_id = MIGRATION_USER_ID
    migration_time = Timestamp()

    candidate_schema = registry.schema.get_schema_branch(name=branch.name).duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    car_schema.attributes.append(AttributeSchema(name="doors", kind="Number", optional=True))
    candidate_schema.set(name="TestCar", schema=car_schema)
    candidate_schema.process()
    car_schema = candidate_schema.get(name="TestCar")

    migration = NodeAttributeAddMigration(
        new_node_schema=car_schema,
        previous_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="doors"),
    )
    execution_result = await migration.execute(
        migration_input=MigrationInput(db=db, at=migration_time, user_id=user_id), branch=branch
    )
    assert not execution_result.errors

    return _AttributeAdd(
        branch=branch,
        node_id=node_uuid,
        migration_time=migration_time,
        user_id=user_id,
        node_before=node_before,
        pre_migration_fingerprint=pre_migration_fingerprint,
        pre_migration_metadata=pre_migration_metadata,
    )


async def _assert_migration_metadata(db: InfrahubDatabase, context: _AttributeAdd) -> None:
    """Assert the add's metadata effect, which differs by branch.

    Vertex metadata is maintained only on the default/global branch, so only there does the add bump
    ``updated_at``/``by`` on the pre-existing node (snapshotting the prior values into ``previous_*``) and
    stamp the freshly-created attribute vertex. On a user branch the shared node is left untouched and the
    new attribute vertex is created without vertex metadata.
    """
    node_after = await get_node_vertex_metadata(db=db, node_uuid=context.node_id)
    attr_after = await get_attribute_vertex_metadata(
        db=db, node_uuid=context.node_id, attribute_name="doors", edge_from=context.migration_time.to_string()
    )
    if context.branch.is_default or context.branch.is_global:
        # The pre-existing node is bumped and its prior values snapshotted so a rollback can restore them.
        assert node_after.updated_at == context.migration_time.to_string()
        assert node_after.updated_by == context.user_id
        assert node_after.previous_updated_at == context.node_before.updated_at
        assert node_after.previous_updated_by == context.node_before.updated_by
        # The attribute vertex is created here, so it is stamped but has no prior value to snapshot.
        assert attr_after.updated_at == context.migration_time.to_string()
        assert attr_after.updated_by == context.user_id
        assert attr_after.previous_updated_at is None
    else:
        # A user-branch add leaves the shared node untouched and creates the attribute without metadata.
        assert node_after == context.node_before
        assert node_after.previous_updated_at is None
        assert attr_after == VertexMetadata()
        assert attr_after == VertexMetadata()


class TestNodeAttributeAddMetadata:
    """On the default branch, adding an attribute stamps vertex metadata and a rollback removes it.

    A class-scoped fixture runs the migration once; the metadata and rollback tests share it and run in
    order (the rollback test reverts the state the metadata test observed).
    """

    @pytest.fixture(scope="class")
    async def context(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
        car_person_schema_scope_class: SchemaBranch,
    ) -> _AttributeAdd:
        person = await Node.init(db=db, schema="TestPerson", branch=default_branch_scope_class)
        await person.new(db=db, name="John", height=180)
        await person.save(db=db)
        car = await Node.init(db=db, schema="TestCar", branch=default_branch_scope_class)
        await car.new(db=db, name="accord", color="#123456", owner=person.id)
        await car.save(db=db)

        return await _run_attribute_add_migration(db=db, branch=default_branch_scope_class, node_uuid=car.id)

    async def test_migration_metadata(self, db: InfrahubDatabase, context: _AttributeAdd) -> None:
        """The add stamps the node and the new attribute vertex and snapshots the node's prior values."""
        await _assert_migration_metadata(db=db, context=context)

    async def test_migration_rollback(self, db: InfrahubDatabase, context: _AttributeAdd) -> None:
        """A range rollback undoes the migration: the added attribute is deleted and the node restored, idempotently."""

        async def _run_rollback() -> None:
            await GraphRollbacker(db=db).rollback(
                target_branch=context.branch,
                at=context.migration_time,
                scope=RollbackScope.SINCE_TIMESTAMP,
            )

        await _run_rollback()
        await verify_graph(db=db)

        # The branch edges and vertex metadata are restored exactly to the pristine pre-setup state.
        assert (
            await branch_edge_fingerprint(db=db, branch_name=context.branch.name) == context.pre_migration_fingerprint
        )
        assert (
            await branch_metadata_fingerprint(db=db, branch_name=context.branch.name) == context.pre_migration_metadata
        )

        # The node metadata is restored to its pre-setup values and the snapshot is cleared.
        node_after = await get_node_vertex_metadata(db=db, node_uuid=context.node_id)
        assert node_after.updated_at == context.node_before.updated_at
        assert node_after.updated_by == context.node_before.updated_by
        assert node_after.previous_updated_at is None
        assert node_after.previous_updated_by is None

        # Running the rollback again is a no-op: nothing remains in the window to revert.
        await _run_rollback()
        await verify_graph(db=db)
        assert (
            await branch_edge_fingerprint(db=db, branch_name=context.branch.name) == context.pre_migration_fingerprint
        )
        assert (
            await branch_metadata_fingerprint(db=db, branch_name=context.branch.name) == context.pre_migration_metadata
        )
        node_again = await get_node_vertex_metadata(db=db, node_uuid=context.node_id)
        assert node_again == node_after


async def test_migration_metadata_non_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node
) -> None:
    """On a user branch the add is reflected through edges but records no vertex-metadata snapshot."""
    branch = await create_branch(branch_name="branch-attr-add-meta", db=db)
    context = await _run_attribute_add_migration(db=db, branch=branch, node_uuid=car_accord_main.id)
    await _assert_migration_metadata(db=db, context=context)


async def test_migration_skips_inherited_attribute_by_default(
    db: InfrahubDatabase, default_branch: Branch, init_database: None, schema_aware_inherited: NodeSchema
) -> None:
    node = schema_aware_inherited

    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 0

    migration = NodeAttributeAddMigration(
        new_node_schema=node,
        previous_node_schema=node,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_doors"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 0
    assert await count_nodes(db=db, label="Attribute") == 0


async def test_migration_force_inherited_creates_attributes(
    db: InfrahubDatabase, default_branch: Branch, init_database: None, schema_aware_inherited: NodeSchema
) -> None:
    node = schema_aware_inherited

    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 0

    migration = NodeAttributeAddMigration(
        new_node_schema=node,
        previous_node_schema=node,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_doors"),
        force_inherited=True,
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 5
    assert await count_nodes(db=db, label="Attribute") == 5

    # A second forced run must be a no-op
    rerun_migration = NodeAttributeAddMigration(
        new_node_schema=node,
        previous_node_schema=node,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_doors"),
        force_inherited=True,
    )
    rerun_result = await rerun_migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

    assert not rerun_result.errors
    assert rerun_result.nbr_migrations_executed == 0
    assert await count_nodes(db=db, label="Attribute") == 5

    await verify_graph(db=db)


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


# -----------------------------------------------------------------------------
# Branch support of the edges created for a new attribute
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class AttributeEdgeBranches:
    """Which branch each live edge of one attribute sits on."""

    branch_support: str
    owning_edge: tuple[str, int]
    property_edges: tuple[tuple[str, str, int], ...]


async def get_attribute_edge_branches(
    db: InfrahubDatabase, node_uuid: str, attribute_name: str
) -> AttributeEdgeBranches:
    query = """
MATCH (n:Node {uuid: $node_uuid})-[e:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
WHERE e.status = "active" AND e.to IS NULL
MATCH (a)-[p]->()
WHERE p.status = "active" AND p.to IS NULL
RETURN a.branch_support AS branch_support,
       collect(DISTINCT [type(p), p.branch, p.branch_level]) AS property_edges,
       e.branch AS owning_branch,
       e.branch_level AS owning_branch_level
    """
    records = await db.execute_query(
        query=query,
        params={"node_uuid": node_uuid, "attribute_name": attribute_name},
        name="attribute_edge_branches",
    )
    assert len(records) == 1, f"expected exactly one open {attribute_name} attribute, got {len(records)}"
    record = records[0]
    return AttributeEdgeBranches(
        branch_support=record["branch_support"],
        owning_edge=(record["owning_branch"], record["owning_branch_level"]),
        property_edges=tuple(sorted(tuple(edge) for edge in record["property_edges"])),
    )


def expected_edges_on(branch_name: str, branch_level: int, branch_support: str) -> AttributeEdgeBranches:
    return AttributeEdgeBranches(
        branch_support=branch_support,
        owning_edge=(branch_name, branch_level),
        property_edges=(
            ("HAS_VALUE", branch_name, branch_level),
            ("IS_PROTECTED", branch_name, branch_level),
        ),
    )


def add_attribute_to_test_car(branch_name: str, attribute: AttributeSchema) -> tuple[NodeSchema, SchemaBranch]:
    """Register a TestCar candidate schema carrying ``attribute`` and return the previous schema with it."""
    previous_schema = registry.schema.get_schema_branch(name=branch_name).get_node(name="TestCar")
    candidate = registry.schema.get_schema_branch(name=branch_name).duplicate()
    car_schema = candidate.get_node(name="TestCar")
    car_schema.attributes.append(attribute)
    candidate.set(name="TestCar", schema=car_schema)
    candidate.process()
    registry.schema.set_schema_branch(name=branch_name, schema=candidate)
    return previous_schema, candidate


async def run_test_car_attribute_add(
    db: InfrahubDatabase, branch: Branch, previous_schema: NodeSchema, candidate: SchemaBranch, attribute_name: str
) -> int:
    migration = NodeAttributeAddMigration(
        new_node_schema=candidate.get_node(name="TestCar"),
        previous_node_schema=previous_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name=attribute_name),
    )
    result = await migration.execute(migration_input=MigrationInput(db=db, at=Timestamp()), branch=branch)
    assert not result.errors
    return result.nbr_migrations_executed


async def read_tag(db: InfrahubDatabase, node_uuid: str, branch: Branch) -> BaseAttribute:
    car = await NodeManager.get_one(db=db, id=node_uuid, branch=branch)
    assert car is not None
    return car.get_attribute(name="tag")


async def test_agnostic_attribute_edges_on_global_branch_from_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    """A branch-agnostic attribute added on the default branch stores its edges on the global branch.

    The profile and template copies of the attribute are covered here too, since the migration expands
    to their kinds off the same declared branch support.
    """
    template_owner = await Node.init(db=db, schema="TemplateTestPerson", branch=default_branch)
    await template_owner.new(db=db, template_name="Template Owner")
    await template_owner.save(db=db)
    template_car = await Node.init(db=db, schema="TemplateTestCar", branch=default_branch)
    await template_car.new(db=db, template_name="Template Accord", color="#111111", owner=template_owner)
    await template_car.save(db=db)
    profile_car = await Node.init(db=db, schema="ProfileTestCar", branch=default_branch)
    await profile_car.new(db=db, profile_name="Profile Accord", profile_priority=1000)
    await profile_car.save(db=db)

    previous_schema, candidate = add_attribute_to_test_car(
        branch_name=default_branch.name,
        attribute=AttributeSchema(name="tag", kind="Text", optional=True, branch=BranchSupportType.AGNOSTIC),
    )

    # The generated schemas carry the declared branch support
    for kind in ("TestCar", "ProfileTestCar", "TemplateTestCar"):
        schema = candidate.get(name=kind, duplicate=False)
        assert schema.get_attribute(name="tag").branch is BranchSupportType.AGNOSTIC

    executed = await run_test_car_attribute_add(
        db=db, branch=default_branch, previous_schema=previous_schema, candidate=candidate, attribute_name="tag"
    )
    # 2 TestCar + 1 TemplateTestCar + 1 ProfileTestCar
    assert executed == 4

    expected = expected_edges_on(
        branch_name=GLOBAL_BRANCH_NAME, branch_level=1, branch_support=BranchSupportType.AGNOSTIC.value
    )
    for node in (car_accord_main, car_camry_main, template_car, profile_car):
        assert await get_attribute_edge_branches(db=db, node_uuid=node.get_id(), attribute_name="tag") == expected

    await assert_no_global_edges_with_wrong_branch_level(db=db)
    await verify_graph(db=db)


async def test_agnostic_attribute_value_is_shared_across_branches(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    """An agnostic attribute added on one branch is stored once, so a value set there reads back elsewhere."""
    migration_branch = await create_branch(branch_name="branch-agnostic-add", db=db)
    sibling_branch = await create_branch(branch_name="branch-agnostic-sibling", db=db)

    agnostic_tag = AttributeSchema(name="tag", kind="Text", optional=True, branch=BranchSupportType.AGNOSTIC)
    previous_schema, candidate = add_attribute_to_test_car(branch_name=migration_branch.name, attribute=agnostic_tag)
    for other_branch in (sibling_branch, default_branch):
        add_attribute_to_test_car(branch_name=other_branch.name, attribute=deepcopy(agnostic_tag))

    executed = await run_test_car_attribute_add(
        db=db, branch=migration_branch, previous_schema=previous_schema, candidate=candidate, attribute_name="tag"
    )
    assert executed == 2

    assert await get_attribute_edge_branches(
        db=db, node_uuid=car_accord_main.get_id(), attribute_name="tag"
    ) == expected_edges_on(
        branch_name=GLOBAL_BRANCH_NAME, branch_level=1, branch_support=BranchSupportType.AGNOSTIC.value
    )

    # One shared vertex, so a value written on one branch is the value every branch reads.
    car_on_migration_branch = await NodeManager.get_one(db=db, id=car_accord_main.get_id(), branch=migration_branch)
    assert car_on_migration_branch is not None
    car_on_migration_branch.get_attribute("tag").value = "shared-tag"
    await car_on_migration_branch.save(db=db, fields=["tag"])

    for branch in (migration_branch, sibling_branch, default_branch):
        assert (await read_tag(db=db, node_uuid=car_accord_main.get_id(), branch=branch)).value == "shared-tag"

    await assert_no_global_edges_with_wrong_branch_level(db=db)
    await verify_graph(db=db)


async def test_aware_attribute_edges_stay_on_migration_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    """A branch-aware attribute keeps its edges on its own branch, so it is not readable elsewhere."""
    migration_branch = await create_branch(branch_name="branch-aware-add", db=db)

    aware_tag = AttributeSchema(name="tag", kind="Text", optional=True, branch=BranchSupportType.AWARE)
    previous_schema, candidate = add_attribute_to_test_car(branch_name=migration_branch.name, attribute=aware_tag)
    add_attribute_to_test_car(branch_name=default_branch.name, attribute=deepcopy(aware_tag))

    executed = await run_test_car_attribute_add(
        db=db, branch=migration_branch, previous_schema=previous_schema, candidate=candidate, attribute_name="tag"
    )
    assert executed == 2

    assert await get_attribute_edge_branches(
        db=db, node_uuid=car_accord_main.get_id(), attribute_name="tag"
    ) == expected_edges_on(
        branch_name=migration_branch.name,
        branch_level=migration_branch.hierarchy_level,
        branch_support=BranchSupportType.AWARE.value,
    )

    # The migration branch resolves the created attribute; the default branch reaches no vertex at all.
    assert (await read_tag(db=db, node_uuid=car_accord_main.get_id(), branch=migration_branch)).db_id is not None
    assert (await read_tag(db=db, node_uuid=car_accord_main.get_id(), branch=default_branch)).db_id is None

    await assert_no_global_edges_with_wrong_branch_level(db=db)
    await verify_graph(db=db)


async def test_agnostic_attribute_add_is_idempotent(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    """The re-run guard still matches an owning edge the previous run put on the global branch."""
    migration_branch = await create_branch(branch_name="branch-agnostic-idempotent", db=db)

    previous_schema, candidate = add_attribute_to_test_car(
        branch_name=migration_branch.name,
        attribute=AttributeSchema(name="tag", kind="Text", optional=True, branch=BranchSupportType.AGNOSTIC),
    )

    assert (
        await run_test_car_attribute_add(
            db=db, branch=migration_branch, previous_schema=previous_schema, candidate=candidate, attribute_name="tag"
        )
        == 2
    )
    attribute_count = await count_nodes(db=db, label="Attribute")

    assert (
        await run_test_car_attribute_add(
            db=db, branch=migration_branch, previous_schema=previous_schema, candidate=candidate, attribute_name="tag"
        )
        == 0
    )
    assert await count_nodes(db=db, label="Attribute") == attribute_count


async def test_migration_agnostic_numberpool_attribute(
    db: InfrahubDatabase,
    branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """An agnostic NumberPool attribute reads back the value the migration allocated for it."""
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    schema_without_pool = NodeSchema(
        name="Server",
        namespace="Test",
        default_filter="name__value",
        branch=BranchSupportType.AWARE,
        attributes=[AttributeSchema(name="name", kind="Text", unique=True, branch=BranchSupportType.AWARE)],
    )
    registry.schema.register_schema(schema=SchemaRoot(nodes=[schema_without_pool]), branch=branch.name)

    servers = []
    for index in range(3):
        server = await Node.init(db=db, schema="TestServer", branch=branch)
        await server.new(db=db, name=f"server-{index}")
        await server.save(db=db)
        servers.append(server)

    schema_with_pool = NodeSchema(
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
                branch=BranchSupportType.AGNOSTIC,
                parameters=NumberPoolParameters(start_range=1, end_range=100),
            ),
        ],
    )
    previous_schema = registry.schema.get_node_schema(name="TestServer", branch=branch)
    registry.schema.set(name="TestServer", schema=schema_with_pool, branch=branch.name)
    registry.schema.process_schema_branch(name=branch.name)

    migration = NodeAttributeAddMigration(
        previous_node_schema=previous_schema,
        new_node_schema=schema_with_pool,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestServer", field_name="rack_unit"),
    )
    result = await migration.execute(migration_input=MigrationInput(db=db, at=Timestamp()), branch=branch)
    assert not result.errors

    servers_map = await NodeManager.get_many(db=db, branch=branch, ids=[server.get_id() for server in servers])
    assert len(servers_map) == 3
    allocated = sorted(servers_map[server.get_id()].get_attribute("rack_unit").value for server in servers)
    assert allocated == [1, 2, 3]

    # The allocated value and the default it replaced live on the same branch, so the default is closed.
    assert await get_attribute_edge_branches(
        db=db, node_uuid=servers[0].get_id(), attribute_name="rack_unit"
    ) == AttributeEdgeBranches(
        branch_support=BranchSupportType.AGNOSTIC.value,
        owning_edge=(GLOBAL_BRANCH_NAME, 1),
        property_edges=(
            ("HAS_SOURCE", GLOBAL_BRANCH_NAME, 1),
            ("HAS_VALUE", GLOBAL_BRANCH_NAME, 1),
            ("IS_PROTECTED", GLOBAL_BRANCH_NAME, 1),
        ),
    )


PROBE_GENERIC = GenericSchema(
    name="Gen",
    namespace="Mixed",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[AttributeSchema(name="name", kind="Text", branch=BranchSupportType.AGNOSTIC)],
)
PROBE_AWARE_NODE = NodeSchema(
    name="Aware",
    namespace="Mixed",
    branch=BranchSupportType.AWARE,
    inherit_from=["MixedGen"],
    attributes=[AttributeSchema(name="name", kind="Text", branch=BranchSupportType.AGNOSTIC)],
)
PROBE_AGNOSTIC_NODE = NodeSchema(
    name="Agn",
    namespace="Mixed",
    branch=BranchSupportType.AGNOSTIC,
    inherit_from=["MixedGen"],
    attributes=[AttributeSchema(name="name", kind="Text", branch=BranchSupportType.AGNOSTIC)],
)


async def test_local_attribute_of_generic_follows_each_node_kind(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Verify an edge case involving a branch-agnostic generic and branch-local/agnostic inheritors.

    If a branch-local attribute is added to a concrete node inheriting from a branch-agnostic generic
    then the new branch-local attribute will
    - be on the global branch if the inheriting schema is branch-agnostic
    - be on the default/user branch if the inheriting schema is branch-aware
    """
    registry.schema.register_schema(
        schema=SchemaRoot(generics=[PROBE_GENERIC], nodes=[PROBE_AWARE_NODE, PROBE_AGNOSTIC_NODE]),
        branch=default_branch.name,
    )
    processed = registry.schema.get_schema_branch(name=default_branch.name)
    previous_schema = processed.get(name="MixedGen", duplicate=False)
    assert sorted(previous_schema.used_by) == ["MixedAgn", "MixedAware"]

    aware_node = await Node.init(db=db, schema="MixedAware", branch=default_branch)
    await aware_node.new(db=db, name="aware-1")
    await aware_node.save(db=db)
    agnostic_node = await Node.init(db=db, schema="MixedAgn", branch=default_branch)
    await agnostic_node.new(db=db, name="agnostic-1")
    await agnostic_node.save(db=db)

    candidate = processed.duplicate()
    generic_schema = candidate.get(name="MixedGen", duplicate=False)
    generic_schema.attributes.append(
        AttributeSchema(name="tag", kind="Text", optional=True, branch=BranchSupportType.LOCAL)
    )
    candidate.set(name="MixedGen", schema=generic_schema)
    candidate.process()
    registry.schema.set_schema_branch(name=default_branch.name, schema=candidate)

    migration = NodeAttributeAddMigration(
        new_node_schema=candidate.get(name="MixedGen", duplicate=False),
        previous_node_schema=previous_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="MixedGen", field_name="tag"),
    )
    result = await migration.execute(migration_input=MigrationInput(db=db, at=Timestamp()), branch=default_branch)
    assert not result.errors
    assert result.nbr_migrations_executed == 2

    # The branch-aware kind keeps the attribute on its own branch...
    assert await get_attribute_edge_branches(
        db=db, node_uuid=aware_node.get_id(), attribute_name="tag"
    ) == expected_edges_on(
        branch_name=default_branch.name,
        branch_level=default_branch.hierarchy_level,
        branch_support=BranchSupportType.LOCAL.value,
    )
    # ...while the branch-agnostic kind stores it once, on the global branch.
    assert await get_attribute_edge_branches(
        db=db, node_uuid=agnostic_node.get_id(), attribute_name="tag"
    ) == expected_edges_on(branch_name=GLOBAL_BRANCH_NAME, branch_level=1, branch_support=BranchSupportType.LOCAL.value)

    await assert_no_global_edges_with_wrong_branch_level(db=db)
    await verify_graph(db=db)
