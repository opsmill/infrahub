from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    SYSTEM_USER_ID,
    InfrahubKind,
    MetadataOptions,
    RelationshipHierarchyDirection,
    SchemaPathType,
)
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration, NodeKindUpdateMigrationQuery01
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.path import SchemaPath
from infrahub.core.query.node import NodeGetHierarchyQuery
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase
from tests.constants import TestKind
from tests.db_snapshot import DbSnapshotter
from tests.helpers.db_validation import validate_node_relationships, verify_no_duplicate_paths
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

    migration = NodeKindUpdateMigration(
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
    migration = NodeKindUpdateMigration(
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

    migration = NodeKindUpdateMigration(
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

    migration = NodeKindUpdateMigration(
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

    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="inherit_from"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2

    # 3. Run the same NodeKindUpdateMigration on the default_branch
    schema_default = registry.schema.get_schema_branch(name=default_branch.name)
    migration_default = NodeKindUpdateMigration(
        previous_node_schema=schema_default.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="inherit_from"),
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

    migration = NodeKindUpdateMigration(
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


async def test_migration_updates_number_pool_node_reference(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that NumberPool.node is updated when the referenced kind is renamed."""
    # 1. Create and register a schema with a NumberPool attribute
    device_schema = NodeSchema(
        name="Device",
        namespace="Test2",
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(
                name="asset_id",
                kind="NumberPool",
                optional=False,
                unique=True,
                read_only=True,
                parameters=NumberPoolParameters(start_range=1000, end_range=9999),
            ),
        ],
    )
    schema = SchemaRoot(nodes=[device_schema])
    await load_schema(db=db, schema=schema)

    # Register the CoreNumberPool type for pool operations (monkeypatched to avoid shared-state pollution)
    monkeypatch.setitem(registry.node, InfrahubKind.NUMBERPOOL, CoreNumberPool)

    # Create a device to trigger pool creation
    device = await Node.init(db=db, schema="Test2Device")
    await device.new(db=db, name="device-01")
    await device.save(db=db)

    # 2. Verify the NumberPool was created with node="Test2Device"
    pools = await registry.manager.query(
        db=db,
        branch=default_branch,
        schema=InfrahubKind.NUMBERPOOL,
        filters={"node": {"value": "Test2Device"}},
    )
    assert len(pools) == 1
    original_pool = pools[0]
    assert original_pool.node.value == "Test2Device"
    pool_id = original_pool.id
    original_pool_name = original_pool.name.value
    assert original_pool_name.startswith("Test2Device.asset_id")

    # 3. Run NodeKindUpdateMigration to rename Test2Device -> Test2NetworkDevice
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema_branch.duplicate()
    old_device_schema = candidate_schema.get(name="Test2Device")
    candidate_schema.delete(name="Test2Device")
    old_device_schema.name = "NetworkDevice"
    candidate_schema.set(name="Test2NetworkDevice", schema=old_device_schema)
    assert old_device_schema.kind == "Test2NetworkDevice"

    migration = NodeKindUpdateMigration(
        previous_node_schema=schema_branch.get(name="Test2Device"),
        new_node_schema=old_device_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NetworkDevice", field_name="name"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors
    # Should have migrated 1 node + 1 pool update
    assert execution_result.nbr_migrations_executed == 2

    # 4. Verify the NumberPool.node and name attributes were updated
    updated_pool = await NodeManager.get_one(db=db, branch=default_branch, id=pool_id)
    assert updated_pool.node.value == "Test2NetworkDevice"
    # Pool name should be updated from "Test2Device.asset_id [...]" to "Test2NetworkDevice.asset_id [...]"
    assert updated_pool.name.value.startswith("Test2NetworkDevice.asset_id")
    assert updated_pool.name.value == original_pool_name.replace("Test2Device.", "Test2NetworkDevice.")

    # 5. Verify pools with new kind name exist
    pools_with_new_name = await registry.manager.query(
        db=db,
        branch=default_branch,
        schema=InfrahubKind.NUMBERPOOL,
        filters={"node": {"value": "Test2NetworkDevice"}},
    )
    assert len(pools_with_new_name) == 1
    assert pools_with_new_name[0].id == pool_id


async def test_migration_updates_ip_address_pool_node_reference(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that CoreIPAddressPool.default_address_type is updated when the referenced kind is renamed."""
    monkeypatch.setitem(registry.node, InfrahubKind.IPADDRESSPOOL, CoreIPAddressPool)

    # 1. Create an IP namespace and a prefix resource required by the pool
    ns = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns.new(db=db, name="test-ns-addr")
    await ns.save(db=db)

    prefix = await Node.init(db=db, schema="IpamIPPrefix")
    await prefix.new(db=db, prefix="192.168.0.0/24", ip_namespace=ns)
    await prefix.save(db=db)

    # 2. Create a CoreIPAddressPool whose default_address_type points to "IpamIPAddress"
    pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)
    pool = await CoreIPAddressPool.init(schema=pool_schema, db=db)
    await pool.new(
        db=db,
        name="IpamIPAddress.test-addr-pool",
        resources=[prefix],
        ip_namespace=ns,
        default_address_type="IpamIPAddress",
    )
    await pool.save(db=db)
    pool_id = pool.id

    # 3. Run NodeKindUpdateMigration to rename IpamIPAddress -> IpamNewIPAddress
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema_branch.duplicate()
    old_addr_schema = candidate_schema.get(name="IpamIPAddress")
    candidate_schema.delete(name="IpamIPAddress")
    old_addr_schema.name = "NewIPAddress"
    candidate_schema.set(name="IpamNewIPAddress", schema=old_addr_schema)
    assert old_addr_schema.kind == "IpamNewIPAddress"

    migration = NodeKindUpdateMigration(
        previous_node_schema=schema_branch.get(name="IpamIPAddress"),
        new_node_schema=old_addr_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="IpamNewIPAddress", field_name="name"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors

    # 4. Verify the pool's default_address_type was updated
    updated_pool = await NodeManager.get_one(db=db, branch=default_branch, id=pool_id)
    assert updated_pool.default_address_type.value == "IpamNewIPAddress"

    # 5. Verify the pool name was updated (it starts with the old kind prefix)
    assert updated_pool.name.value.startswith("IpamNewIPAddress.")


async def test_migration_updates_ip_prefix_pool_node_reference(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that CoreIPPrefixPool.default_prefix_type is updated when the referenced kind is renamed."""
    monkeypatch.setitem(registry.node, InfrahubKind.IPPREFIXPOOL, CoreIPPrefixPool)

    # 1. Create an IP namespace and a prefix resource required by the pool
    ns = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns.new(db=db, name="test-ns-prefix")
    await ns.save(db=db)

    prefix = await Node.init(db=db, schema="IpamIPPrefix")
    await prefix.new(db=db, prefix="10.0.0.0/8", ip_namespace=ns)
    await prefix.save(db=db)

    # 2. Create a CoreIPPrefixPool whose default_prefix_type points to "IpamIPPrefix"
    pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)
    pool = await CoreIPPrefixPool.init(schema=pool_schema, db=db)
    await pool.new(
        db=db,
        name="IpamIPPrefix.test-prefix-pool",
        resources=[prefix],
        ip_namespace=ns,
        default_prefix_length=24,
        default_prefix_type="IpamIPPrefix",
    )
    await pool.save(db=db)
    pool_id = pool.id

    # 3. Run NodeKindUpdateMigration to rename IpamIPPrefix -> IpamNewIPPrefix
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema_branch.duplicate()
    old_prefix_schema = candidate_schema.get(name="IpamIPPrefix")
    candidate_schema.delete(name="IpamIPPrefix")
    old_prefix_schema.name = "NewIPPrefix"
    candidate_schema.set(name="IpamNewIPPrefix", schema=old_prefix_schema)
    assert old_prefix_schema.kind == "IpamNewIPPrefix"

    migration = NodeKindUpdateMigration(
        previous_node_schema=schema_branch.get(name="IpamIPPrefix"),
        new_node_schema=old_prefix_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="IpamNewIPPrefix", field_name="name"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors

    # 4. Verify the pool's default_prefix_type was updated
    updated_pool = await NodeManager.get_one(db=db, branch=default_branch, id=pool_id)
    assert updated_pool.default_prefix_type.value == "IpamNewIPPrefix"

    # 5. Verify the pool name was updated (it starts with the old kind prefix)
    assert updated_pool.name.value.startswith("IpamNewIPPrefix.")
