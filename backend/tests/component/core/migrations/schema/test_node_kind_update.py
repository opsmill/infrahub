from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    SYSTEM_USER_ID,
    BranchSupportType,
    InfrahubKind,
    MetadataOptions,
    NumberPoolType,
    RelationshipHierarchyDirection,
    SchemaPathType,
)
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.migrations.schema.node_kind_update import (
    NodeInheritFromUpdateMigration,
    NodeKindUpdateMigrationQuery01,
    NodeNamespaceUpdateMigration,
    NodeNameUpdateMigration,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.path import SchemaPath
from infrahub.core.query.node import NodeGetHierarchyQuery
from infrahub.core.schema import AttributeSchema, GenericSchema, MainSchemaTypes, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.definitions.core.template import core_object_component_template, core_object_template
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase
from tests.constants import TestKind
from tests.db_snapshot import DbSnapshotter
from tests.helpers.db_validation import validate_node_relationships, verify_graph, verify_no_duplicate_paths
from tests.helpers.edge_timestamps import assert_edge_timestamps
from tests.helpers.schema import LOCATION_SCHEMA, load_schema


async def test_query_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    candidate_schema.delete(name="TestCar")
    car_schema.name = "NewCar"
    car_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewCar", schema=car_schema)
    assert car_schema.kind == "Test2NewCar"

    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 0

    count_rels = await count_relationships(db=db)

    migration = NodeNamespaceUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"),
    )
    query = await NodeKindUpdateMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 2

    # we expect 14 new relationships per TestCar, 36 TOTAL
    # 2 x 8 attributes = 16
    # 2 x 1 relationship = 2
    # 2 for the root node = 2
    assert await count_relationships(db=db) == count_rels + 36
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 2

    # Re-execute the query once to ensure that it won't change anything
    query = await NodeKindUpdateMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0
    assert await count_relationships(db=db) == count_rels + 36
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 2


async def test_migration_aware_relationship(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    candidate_schema.delete(name="TestCar")
    car_schema.name = "NewCar"
    car_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewCar", schema=car_schema)
    assert car_schema.kind == "Test2NewCar"

    # 1. Snapshot before migration
    snapshotter = DbSnapshotter(db)
    before_snapshot = await snapshotter.snapshot()

    # 2. Create explicit timestamp
    at = Timestamp()
    at_str = at.to_string()

    # 3. Count nodes and relationships before migration
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 0
    count_rels = await count_relationships(db=db)

    # 4. Execute migration
    migration = NodeNamespaceUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="namespace"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2

    # 5. Validate nodes and relationships after migration
    assert await count_relationships(db=db) == count_rels + 36
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 2

    # 6. Validate edge timestamps
    after_snapshot = await snapshotter.snapshot()
    assert_edge_timestamps(before_snapshot, after_snapshot, at_str)

    # 7. Validate node relationships
    await validate_node_relationships(node=car_accord_main, db=db, branch=default_branch)
    await validate_node_relationships(node=car_camry_main, db=db, branch=default_branch)


async def test_migration_agnostic_relationship(
    db: InfrahubDatabase, default_branch: Branch, car_person_branch_agnostic_schema: dict[str, Any]
) -> None:
    await load_schema(db=db, schema=SchemaRoot(**car_person_branch_agnostic_schema))

    person_john = await Node.init(db=db, schema="TestPerson")
    await person_john.new(db=db, name={"value": "John"})
    await person_john.save(db=db)

    car = await Node.init(db=db, schema="TestCar")
    await car.new(db=db, name="yaris", agnostic_owner=person_john.id)
    await car.save(db=db)

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    candidate_schema.delete(name="TestCar")
    car_schema.name = "NewCar"
    car_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewCar", schema=car_schema)
    assert car_schema.kind == "Test2NewCar"

    assert await count_nodes(db=db, label="TestCar") == 1
    assert await count_nodes(db=db, label="Test2NewCar") == 0

    migration = NodeNamespaceUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="namespace"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 1
    assert await count_nodes(db=db, label="TestCar") == 1
    assert await count_nodes(db=db, label="Test2NewCar") == 1

    await validate_node_relationships(node=person_john, db=db, branch=registry.get_global_branch())
    await validate_node_relationships(node=car, db=db, branch=registry.get_global_branch())


async def test_migration_hierarchy(db: InfrahubDatabase, default_branch: Branch) -> None:
    await load_schema(db=db, schema=LOCATION_SCHEMA)

    continent_europe = await Node.init(db=db, schema=TestKind.CONTINENT)
    await continent_europe.new(db=db, name={"value": "Europe"}, shortname={"value": "EU"})
    await continent_europe.save(db=db)

    country_france = await Node.init(db=db, schema=TestKind.COUNTRY)
    await country_france.new(db=db, name="France", shortname={"value": "FR"}, parent=continent_europe.id)
    await country_france.save(db=db)

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    continent_schema = candidate_schema.get(name=TestKind.CONTINENT)
    candidate_schema.delete(name=TestKind.CONTINENT)
    continent_schema.name = "NewContinent"
    continent_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewContinent", schema=continent_schema)
    assert continent_schema.kind == "Test2NewContinent"
    candidate_schema.get(name=TestKind.COUNTRY, duplicate=False).parent = "Test2NewContinent"

    assert await count_nodes(db=db, label=TestKind.CONTINENT) == 1
    assert await count_nodes(db=db, label="Test2NewContinent") == 0

    migration = NodeNamespaceUpdateMigration(
        previous_node_schema=schema.get(name=TestKind.CONTINENT),
        new_node_schema=continent_schema,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind=TestKind.CONTINENT, field_name="namespace"
        ),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 1
    assert await count_nodes(db=db, label=TestKind.CONTINENT) == 1
    assert await count_nodes(db=db, label="Test2NewContinent") == 1

    country_schema = schema.get(name=TestKind.COUNTRY, duplicate=False)
    assert country_schema.parent == "Test2NewContinent"

    hierarchy_query = await NodeGetHierarchyQuery.init(
        db=db,
        direction=RelationshipHierarchyDirection.ANCESTORS,
        node_id=country_france.id,
        node_schema=country_schema,
        branch=default_branch,
    )
    await hierarchy_query.execute(db=db)
    assert list(hierarchy_query.get_peer_ids()) == [continent_europe.get_id()]


async def test_inheritance_migration_on_branch_and_main(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node, person_alfred_main: Node
) -> None:
    # 0. add a deleted relationship
    accord_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    await accord_main.owner.update(db=db, data=person_alfred_main.id)
    await accord_main.save(db=db)

    # 1. Create a new branch
    branch = await create_branch(db=db, branch_name="test-migration-branch")

    # 2. Run NodeKindUpdateMigration on the new branch
    schema = registry.schema.get_schema_branch(name=branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get_node(name="TestCar")
    candidate_schema.delete(name="TestCar")
    car_schema.inherit_from = ["GenericThing"]
    candidate_schema.set(name="TestCar", schema=car_schema)

    migration = NodeInheritFromUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2

    # 3. Run the same NodeKindUpdateMigration on the default_branch
    schema_default = registry.schema.get_schema_branch(name=default_branch.name)
    migration_default = NodeInheritFromUpdateMigration(
        previous_node_schema=schema_default.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )

    execution_result_default = await migration_default.execute(
        migration_input=MigrationInput(db=db), branch=default_branch
    )
    assert not execution_result_default.errors

    await verify_no_duplicate_paths(db=db)


async def test_migration_metadata(db: InfrahubDatabase, car_accord_main: Node, branch: Branch) -> None:
    """Test that metadata is set correctly when updating node kind."""
    car_created_at = car_accord_main._get_created_at()
    schema = registry.schema.get_schema_branch(name=branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    candidate_schema.delete(name="TestCar")
    car_schema.name = "NewCar"
    car_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewCar", schema=car_schema)

    test_user_id = "test-metadata-user"
    migration_time = Timestamp()

    migration = NodeNamespaceUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"),
    )
    execution_result = await migration.execute(
        migration_input=MigrationInput(db=db, at=migration_time, user_id=test_user_id), branch=branch
    )
    assert not execution_result.errors

    registry.schema.set_schema_branch(name=branch.name, schema=candidate_schema)

    updated_car = await NodeManager.get_one(
        db=db,
        branch=branch,
        id=car_accord_main.id,
        include_metadata=MetadataQueryOptions(
            node_level=MetadataOptions.USER_TIMESTAMPS,
            attribute_level=MetadataOptions.USER_TIMESTAMPS,
            relationship_level=MetadataOptions.USER_TIMESTAMPS,
        ),
        prefetch_relationships=True,
    )
    assert updated_car._get_created_at() == car_created_at
    assert updated_car._get_created_by() == SYSTEM_USER_ID
    assert updated_car._get_updated_at() == migration_time
    assert updated_car._get_updated_by() == test_user_id
    for attr_name in car_schema.attribute_names:
        attr = updated_car.get_attribute(name=attr_name)
        assert attr._get_created_at() == car_created_at
        assert attr._get_created_by() == SYSTEM_USER_ID
        assert attr._get_updated_at() == attr._get_created_at()
        assert attr._get_updated_by() == SYSTEM_USER_ID
    rel_manager = updated_car.get_relationship(name="owner")
    rel = await rel_manager.get(db=db)
    assert rel._get_created_at() == car_created_at
    assert rel._get_created_by() == SYSTEM_USER_ID
    assert rel._get_updated_at() == rel._get_created_at()
    assert rel._get_updated_by() == SYSTEM_USER_ID

    # Query for the NEW active node edges and verify metadata
    query = """
    MATCH (n:Test2NewCar {uuid: $node_uuid})-[r {branch: $branch, status: "active", from: $migration_time}]-()
    RETURN DISTINCT r.from_user_id as from_user_id
    """
    results = await db.execute_query(
        query=query,
        params={"node_uuid": car_accord_main.id, "branch": branch.name, "migration_time": migration_time.to_string()},
    )
    assert len(results) == 1, "Expected exactly one active edge on migrated node"
    assert results[0]["from_user_id"] == test_user_id

    # Query for the OLD deleted node edges and verify metadata
    query = """
    MATCH (n:TestCar {uuid: $node_uuid})-[r {branch: $branch, status: "deleted", from: $migration_time}]-()
    RETURN DISTINCT r.from_user_id as from_user_id
    """
    results = await db.execute_query(
        query=query,
        params={"node_uuid": car_accord_main.id, "branch": branch.name, "migration_time": migration_time.to_string()},
    )
    assert len(results) == 1, "Expected exactly one deleted edge on old node"
    assert results[0]["from_user_id"] == test_user_id


# -----------------------------------------------------------------------------
# Newly-inherited attribute tests
# -----------------------------------------------------------------------------


@pytest.fixture
async def car_person_template_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> SchemaBranch:
    registry.schema.register_schema(
        schema=SchemaRoot(generics=[core_object_template, core_object_component_template]), branch=default_branch.name
    )
    for node in car_person_schema_unregistered.nodes:
        node.generate_template = True
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


def _make_kind_inherit_generic(
    branch: Branch, generic: GenericSchema, kind: str
) -> tuple[MainSchemaTypes, MainSchemaTypes]:
    """Register the generic, add it to the kind's inherit_from and reprocess the schema branch.

    Returns the (previous, new) node schemas around the change.
    """
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous_schema = schema_branch.get(name=kind, duplicate=True)

    registry.schema.set(name=generic.kind, schema=generic, branch=branch.name)
    node_schema = schema_branch.get_node(name=kind, duplicate=True)
    node_schema.inherit_from = list(node_schema.inherit_from) + [generic.kind]
    registry.schema.set(name=kind, schema=node_schema, branch=branch.name)
    registry.schema.process_schema_branch(name=branch.name)

    new_schema = registry.schema.get(name=kind, branch=branch.name, duplicate=False)
    return previous_schema, new_schema


async def _count_attribute_vertices(db: InfrahubDatabase, node_label: str, attribute_name: str) -> int:
    query = """
    MATCH (n:%(node_label)s)-[:HAS_ATTRIBUTE]->(a:Attribute { name: $attr_name })
    RETURN count(a) AS attr_count
    """ % {"node_label": node_label}
    results = await db.execute_query(query=query, params={"attr_name": attribute_name})
    return results[0]["attr_count"]


async def test_migration_newly_inherited_attributes(
    db: InfrahubDatabase, default_branch: Branch, car_person_template_schema: SchemaBranch
) -> None:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="John", height=180)
    await person.save(db=db)

    car_accord = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car_accord.new(db=db, name="accord", nbr_seats=5, is_electric=True, owner=person)
    await car_accord.save(db=db)
    car_camry = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car_camry.new(db=db, name="camry", nbr_seats=5, is_electric=False, owner=person)
    await car_camry.save(db=db)

    profile = await Node.init(db=db, schema="ProfileTestCar", branch=default_branch)
    await profile.new(db=db, profile_name="car-profile1", nbr_seats=4)
    await profile.save(db=db)

    template_person = await Node.init(db=db, schema="TemplateTestPerson", branch=default_branch)
    await template_person.new(db=db, template_name="Template Person 1")
    await template_person.save(db=db)
    template_car = await Node.init(db=db, schema="TemplateTestCar", branch=default_branch)
    await template_car.new(db=db, template_name="Template Car 1", nbr_seats=5, owner=template_person)
    await template_car.save(db=db)

    generic = GenericSchema(
        name="Asset",
        namespace="Test",
        branch=BranchSupportType.AWARE,
        attributes=[
            AttributeSchema(name="status", kind="Text", default_value="active", optional=True),
            AttributeSchema(name="serial", kind="Text", unique=True, optional=True),
        ],
    )
    previous_schema, new_schema = _make_kind_inherit_generic(branch=default_branch, generic=generic, kind="TestCar")

    migration = NodeInheritFromUpdateMigration(
        previous_node_schema=previous_schema,
        new_node_schema=new_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

    assert not execution_result.errors
    # the counter aggregates the duplicated vertices with the attribute rows created by the
    # sub-migrations: 2 duplicated cars + (status on 2 cars, 1 profile and 1 template) + serial on 2 cars
    assert execution_result.nbr_migrations_executed == 8

    assert await _count_attribute_vertices(db=db, node_label="TestCar", attribute_name="status") == 2
    assert await _count_attribute_vertices(db=db, node_label="ProfileTestCar", attribute_name="status") == 1
    assert await _count_attribute_vertices(db=db, node_label="TemplateTestCar", attribute_name="status") == 1

    # The unique attribute must not land on profile or template instances
    assert await _count_attribute_vertices(db=db, node_label="TestCar", attribute_name="serial") == 2
    assert await _count_attribute_vertices(db=db, node_label="ProfileTestCar", attribute_name="serial") == 0
    assert await _count_attribute_vertices(db=db, node_label="TemplateTestCar", attribute_name="serial") == 0

    # Reads return a real attribute with the generic's default value
    accord = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord.id)
    status_attr = accord.get_attribute(name="status")
    assert status_attr.id is not None
    assert status_attr.value == "active"
    assert status_attr.is_default is True

    profile_node = await NodeManager.get_one(db=db, branch=default_branch, id=profile.id)
    assert profile_node.get_attribute(name="status").id is not None

    # Updates persist across a re-read
    status_attr.value = "maintenance"
    await accord.save(db=db)
    accord_refreshed = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord.id)
    assert accord_refreshed.get_attribute(name="status").value == "maintenance"
    assert accord_refreshed.get_attribute(name="status").is_default is False

    # Attribute-value filters match
    matches = await NodeManager.query(
        db=db, schema="TestCar", filters={"status__value": "active"}, branch=default_branch
    )
    assert [node.id for node in matches] == [car_camry.id]

    await verify_no_duplicate_paths(db=db)


async def test_migration_newly_inherited_numberpool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool

    server_schema = NodeSchema(
        name="Server",
        namespace="Test",
        branch=BranchSupportType.AWARE,
        attributes=[AttributeSchema(name="name", kind="Text", unique=True, branch=BranchSupportType.AWARE)],
    )
    registry.schema.register_schema(schema=SchemaRoot(nodes=[server_schema]), branch=default_branch.name)

    servers = []
    for index in range(3):
        server = await Node.init(db=db, schema="TestServer", branch=default_branch)
        await server.new(db=db, name=f"server-{index}")
        await server.save(db=db)
        servers.append(server)

    generic = GenericSchema(
        name="Asset",
        namespace="Test",
        branch=BranchSupportType.AWARE,
        attributes=[
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
    previous_schema, new_schema = _make_kind_inherit_generic(branch=default_branch, generic=generic, kind="TestServer")

    migration = NodeInheritFromUpdateMigration(
        previous_node_schema=previous_schema,
        new_node_schema=new_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestServer"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors

    # Exactly one pool exists and it is registered against the generic's kind
    pools = await NodeManager.query(
        db=db,
        schema="CoreNumberPool",
        filters={"pool_type__value": NumberPoolType.SCHEMA.value},
        branch_agnostic=True,
    )
    assert len(pools) == 1
    assert pools[0].get_attribute(name="node").value == "TestAsset"
    assert pools[0].get_attribute(name="node_attribute").value == "rack_unit"

    # Every pre-existing node received a distinct allocated number from the pool
    servers_map = await NodeManager.get_many(db=db, branch=default_branch, ids=[server.id for server in servers])
    rack_units = [server.get_attribute(name="rack_unit").value for server in servers_map.values()]
    assert all(value is not None for value in rack_units)
    assert len(set(rack_units)) == 3
    for value in rack_units:
        assert isinstance(value, int)
        assert 1 <= value <= 100


async def test_migration_name_update_creates_no_attributes(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    candidate_schema.delete(name="TestCar")
    car_schema.name = "NewCar"
    car_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewCar", schema=car_schema)

    count_attrs = await count_nodes(db=db, label="Attribute")

    migration = NodeNamespaceUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2
    assert await count_nodes(db=db, label="Attribute") == count_attrs

    await verify_graph(db=db)


async def test_migration_rename_skips_newly_inherited_attributes(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    """A rename that coincides with an inheritance change must leave the attribute rows to the inheritance path."""
    generic = GenericSchema(
        name="Asset",
        namespace="Test",
        branch=BranchSupportType.AWARE,
        attributes=[AttributeSchema(name="status", kind="Text", default_value="active", optional=True)],
    )
    previous_schema, new_schema = _make_kind_inherit_generic(branch=default_branch, generic=generic, kind="TestCar")

    for migration_class, field_name in [
        (NodeNameUpdateMigration, "name"),
        (NodeNamespaceUpdateMigration, "namespace"),
    ]:
        migration = migration_class(
            previous_node_schema=previous_schema,
            new_node_schema=new_schema,
            schema_path=SchemaPath(
                path_type=SchemaPathType.NODE, schema_kind="TestCar", field_name=field_name, property_name=field_name
            ),
        )

        execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
        assert not execution_result.errors
        assert await _count_attribute_vertices(db=db, node_label="TestCar", attribute_name="status") == 0

    # the same schema pair through the inherit_from migration does create the rows
    inheritance_migration = NodeInheritFromUpdateMigration(
        previous_node_schema=previous_schema,
        new_node_schema=new_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )
    inheritance_result = await inheritance_migration.execute(
        migration_input=MigrationInput(db=db), branch=default_branch
    )
    assert not inheritance_result.errors
    assert await _count_attribute_vertices(db=db, node_label="TestCar", attribute_name="status") == 2

    await verify_graph(db=db)


async def test_migration_partial_failure_rerun_converges(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    generic = GenericSchema(
        name="Asset",
        namespace="Test",
        branch=BranchSupportType.AWARE,
        attributes=[AttributeSchema(name="status", kind="Text", default_value="active", optional=True)],
    )
    previous_schema, new_schema = _make_kind_inherit_generic(branch=default_branch, generic=generic, kind="TestCar")

    migration = NodeInheritFromUpdateMigration(
        previous_node_schema=previous_schema,
        new_node_schema=new_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )

    # Simulate a failure after vertex duplication but before the attribute rows are created
    duplication_query = await migration.queries[0].init(db=db, branch=default_branch, migration=migration)
    await duplication_query.execute(db=db)
    assert duplication_query.get_nbr_migrations_executed() == 2
    assert await _count_attribute_vertices(db=db, node_label="TestCar", attribute_name="status") == 0

    # A rerun of the full migration converges to the complete state
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2
    assert await _count_attribute_vertices(db=db, node_label="TestCar", attribute_name="status") == 2

    # A second full rerun performs no work
    rerun_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not rerun_result.errors
    assert rerun_result.nbr_migrations_executed == 0
    assert await _count_attribute_vertices(db=db, node_label="TestCar", attribute_name="status") == 2

    await verify_graph(db=db)


async def test_migration_previous_schema_already_carrying_the_attributes_creates_no_rows(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    """An already-migrated previous_schema makes the sub-migrations create nothing.

    The newly-inherited set is computed against previous_schema, so a caller that supplies a
    previous_schema already carrying the attributes gets a silent no-op — no error, just
    instances left without rows. Callers must pass a baseline that predates the inheritance.
    """
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="John", height=180)
    await person.save(db=db)

    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="accord", nbr_seats=5, is_electric=True, owner=person)
    await car.save(db=db)

    generic = GenericSchema(
        name="Audited",
        namespace="Test",
        branch=BranchSupportType.AWARE,
        attributes=[AttributeSchema(name="audit_state", kind="Text", default_value="unreviewed", optional=True)],
    )
    _, new_schema = _make_kind_inherit_generic(branch=default_branch, generic=generic, kind="TestCar")

    schema_path = SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar")

    # previous_schema already carries audit_state, exactly as the rebase supplies it when the
    # inheritance arrives from the base branch rather than from the branch's own schema.
    migration = NodeInheritFromUpdateMigration(
        previous_node_schema=new_schema,
        new_node_schema=new_schema,
        schema_path=schema_path,
    )
    assert migration._newly_inherited_attributes() == []

    result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not result.errors
    assert await _count_attribute_vertices(db=db, node_label="TestCar", attribute_name="audit_state") == 0

    accord = await NodeManager.get_one(db=db, branch=default_branch, id=car.id)
    assert accord.get_attribute(name="audit_state").id is None

    # With a previous_schema that predates the inheritance, the same migration repairs the node.
    previous_without_generic = new_schema.duplicate()
    previous_without_generic.inherit_from = [
        kind for kind in previous_without_generic.inherit_from if kind != generic.kind
    ]
    previous_without_generic.attributes = [
        attribute for attribute in previous_without_generic.attributes if attribute.name != "audit_state"
    ]
    repairing_migration = NodeInheritFromUpdateMigration(
        previous_node_schema=previous_without_generic,
        new_node_schema=new_schema,
        schema_path=schema_path,
    )
    assert [attribute.name for attribute in repairing_migration._newly_inherited_attributes()] == ["audit_state"]

    repair_result = await repairing_migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not repair_result.errors
    assert await _count_attribute_vertices(db=db, node_label="TestCar", attribute_name="audit_state") == 1

    accord_repaired = await NodeManager.get_one(db=db, branch=default_branch, id=car.id)
    assert accord_repaired.get_attribute(name="audit_state").id is not None
    assert accord_repaired.get_attribute(name="audit_state").value == "unreviewed"
