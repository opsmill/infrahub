"""Two node-kind/inheritance migrations applied in sequence on one branch."""

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    SYSTEM_USER_ID,
    MetadataOptions,
    SchemaPathType,
)
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.metadata.query.node_metadata import NodeMetadataDefaultBranchQuery
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import NodeNotFoundError, SchemaNotFoundError
from tests.helpers.db_validation import verify_graph
from tests.node_creation import create_and_save

from .conftest import get_diff_coordinator, get_diff_merger


async def test_diff_and_merge_with_migrated_node_kind_and_migrated_inheritance(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_generics: SchemaBranch,
) -> None:
    # schema with multiple generics
    root_with_another_generic = SchemaRoot(
        generics=[
            GenericSchema(
                name="Vehicle",
                namespace="Test",
                attributes=[AttributeSchema(name="speed", kind="Text", optional=True)],
            )
        ]
    )
    registry.schema.register_schema(schema=root_with_another_generic, branch=default_branch.name)
    schema_main = registry.schema.get_schema_branch(name=default_branch.name)
    await registry.schema.update_schema_branch(db=db, branch=default_branch, schema=schema_main, update_db=True)

    # initial data
    person_1 = await create_and_save(db=db, branch=default_branch, schema="TestPerson", name="One", height=171)
    person_2 = await create_and_save(db=db, branch=default_branch, schema="TestPerson", name="Two", height=172)
    person_3 = await create_and_save(db=db, branch=default_branch, schema="TestPerson", name="Three", height=173)
    await create_and_save(
        db=db, branch=default_branch, schema="TestGazCar", name="Gaz", nbr_seats=3, mpg=32, owner=person_1
    )
    e_car_1 = await create_and_save(
        db=db,
        branch=default_branch,
        schema="TestElectricCar",
        name="Eee",
        nbr_seats=4,
        nbr_engine=1,
        owner=person_2,
    )
    e_car_1_created_at = e_car_1._get_created_at()
    e_car_2 = await create_and_save(
        db=db,
        branch=default_branch,
        schema="TestElectricCar",
        name="Eee2",
        nbr_seats=5,
        nbr_engine=2,
        owner=person_3,
    )
    e_car_2_created_at = e_car_2._get_created_at()
    original_e_car_1_owner = person_2

    # new branch
    branch2 = await create_branch(db=db, branch_name="branch2")

    # migrate TestElectricCar to be Test2NewElectricCar
    schema_branch = registry.schema.get_schema_branch(name=branch2.name)
    original_car_schema = schema_branch.get(name="TestElectricCar", duplicate=True)
    car_schema_branch = schema_branch.get(name="TestElectricCar", duplicate=True)
    car_schema_branch.name = "NewElectricCar"
    car_schema_branch.namespace = "Test2"
    assert car_schema_branch.kind == "Test2NewElectricCar"
    schema_branch.set(name="Test2NewElectricCar", schema=car_schema_branch)
    schema_branch.process()
    await registry.schema.update_schema_branch(
        db=db,
        branch=branch2,
        schema=schema_branch,
        limit=["TestElectricCar", "Test2NewElectricCar"],
        update_db=True,
    )
    migration = NodeKindUpdateMigration(
        previous_node_schema=schema_branch.get(name="TestElectricCar"),
        new_node_schema=car_schema_branch,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewElectricCar", field_name="namespace"
        ),
    )
    migration1_at = Timestamp()
    execution_result = await migration.execute(
        migration_input=MigrationInput(db=db, at=migration1_at, user_id="migration-user-one"), branch=branch2
    )
    assert not execution_result.errors

    # update car owner
    migrated_car = await NodeManager.get_one(db=db, branch=branch2, id=e_car_1.id)
    await migrated_car.owner.update(db=db, data=person_1.id)
    new_color = "#654321"
    migrated_car.color.value = new_color
    await migrated_car.save(db=db, user_id="branch-user")

    # migrate Test2NewElectricCar to inherit from TestVehicle
    schema_branch = registry.schema.get_schema_branch(name=branch2.name)
    car_schema_branch = schema_branch.get(name="Test2NewElectricCar", duplicate=True)
    car_schema_branch.inherit_from += ["TestVehicle"]
    schema_branch.set(name="Test2ElectricNewCar", schema=car_schema_branch)
    schema_branch.process()
    await registry.schema.update_schema_branch(
        db=db, branch=branch2, schema=schema_branch, limit=["Test2NewElectricCar"], update_db=True
    )
    migration = NodeKindUpdateMigration(
        previous_node_schema=schema_branch.get(name="Test2NewElectricCar"),
        new_node_schema=car_schema_branch,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewElectricCar", field_name="inherit_from"
        ),
    )
    migration2_at = Timestamp()
    execution_result = await migration.execute(
        migration_input=MigrationInput(db=db, at=migration2_at, user_id="migration-user-two"), branch=branch2
    )
    assert not execution_result.errors

    # delete a car
    migrated_car_to_delete = await NodeManager.get_one(db=db, branch=branch2, id=e_car_2.id)
    await migrated_car_to_delete.delete(db=db, user_id="branch-user-delete")

    merge_at = Timestamp()
    diff_coordinator = await get_diff_coordinator(db=db, branch=branch2)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch2)
    diff_merger = await get_diff_merger(db=db, branch=branch2)
    await diff_merger.merge_graph(at=merge_at)

    updated_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    registry.schema.set_schema_branch(name=default_branch.name, schema=updated_schema_branch)
    car_schema_main = updated_schema_branch.get(name="Test2NewElectricCar", duplicate=False)
    assert "TestVehicle" in car_schema_main.inherit_from
    assert car_schema_main.id == original_car_schema.id
    with pytest.raises(SchemaNotFoundError):
        updated_schema_branch.get(name="TestElectricCar", duplicate=False)

    retrieved_migrated_car = await NodeManager.get_one(db=db, branch=default_branch, id=e_car_1.id)
    assert retrieved_migrated_car.get_kind() == "Test2NewElectricCar"
    for attr_name in car_schema_main.attribute_names:
        if attr_name == "color":
            assert retrieved_migrated_car.color.value == new_color
        elif attr_name == "speed":
            assert retrieved_migrated_car.speed is not None
            assert not hasattr(e_car_1, "speed")
        else:
            assert getattr(retrieved_migrated_car, attr_name).value == getattr(e_car_1, attr_name).value
    retrieved_owner_rels = await retrieved_migrated_car.owner.get_relationships(db=db)
    assert {r.get_peer_id() for r in retrieved_owner_rels} == {person_1.id}
    with pytest.raises(SchemaNotFoundError):
        await NodeManager.query(db=db, branch=default_branch, schema="TestElectricCar")
    # try to get deleted node
    with pytest.raises(NodeNotFoundError):
        await NodeManager.get_one(db=db, branch=branch2, id=e_car_2.id, raise_on_error=True)

    # Validate node-level metadata on migrated car after merge
    migrated_car_with_metadata = await NodeManager.get_one(
        db=db,
        branch=default_branch,
        id=e_car_1.id,
        include_metadata=MetadataQueryOptions(
            node_level=MetadataOptions.USER_TIMESTAMPS,
            attribute_level=MetadataOptions.USER_TIMESTAMPS,
            relationship_level=MetadataOptions.USER_TIMESTAMPS,
        ),
        prefetch_relationships=True,
    )
    # Node created_at is from first migration time (when the new kind was created on branch)
    assert migrated_car_with_metadata._get_created_at() == e_car_1_created_at
    assert migrated_car_with_metadata._get_created_by() == SYSTEM_USER_ID
    # Node was updated by branch-user at branch update time
    assert migrated_car_with_metadata._get_updated_at() == merge_at
    assert migrated_car_with_metadata._get_updated_by() == "branch-user"

    # Validate attribute-level metadata on migrated car after merge
    # Color attribute was updated by branch-user
    assert migrated_car_with_metadata.color._get_created_at() == e_car_1_created_at
    assert migrated_car_with_metadata.color._get_created_by() == SYSTEM_USER_ID
    assert migrated_car_with_metadata.color._get_updated_at() == merge_at
    assert migrated_car_with_metadata.color._get_updated_by() == "branch-user"

    # Other attributes should have migration1 created_at, updated_at from last migration
    assert migrated_car_with_metadata.name._get_created_at() == e_car_1_created_at
    assert migrated_car_with_metadata.name._get_created_by() == SYSTEM_USER_ID
    assert migrated_car_with_metadata.name._get_updated_at() == e_car_1_created_at
    assert migrated_car_with_metadata.name._get_updated_by() == SYSTEM_USER_ID

    # Validate relationship-level metadata on migrated car after merge
    # Owner relationship was updated by branch-user
    owner_rel = await migrated_car_with_metadata.owner.get(db=db)
    assert owner_rel._get_created_at() == merge_at
    assert owner_rel._get_created_by() == "branch-user"
    assert owner_rel._get_updated_at() == merge_at
    assert owner_rel._get_updated_by() == "branch-user"

    # Validate metadata on deleted car using NodeMetadataDefaultBranchQuery
    node_metadata_query = await NodeMetadataDefaultBranchQuery.init(
        db=db,
        branch=default_branch,
        node_uuids=[e_car_2.id],
    )
    await node_metadata_query.execute(db=db)
    node_metadatas = node_metadata_query.get_metadatas()
    assert len(node_metadatas) == 1

    deleted_car_meta = node_metadatas[0]
    assert deleted_car_meta.uuid == e_car_2.id
    assert deleted_car_meta.is_deleted is True
    # Deleted car should have migration1 created_at, updated_at from branch user delete
    assert deleted_car_meta.created_at == e_car_2_created_at
    assert deleted_car_meta.created_by == SYSTEM_USER_ID
    assert deleted_car_meta.updated_at == merge_at
    assert deleted_car_meta.updated_by == "branch-user-delete"

    # Validate deleted car's attributes metadata
    for attr in deleted_car_meta.attributes:
        assert attr.is_deleted is True
        assert attr.created_at == e_car_2_created_at
        assert attr.created_by == SYSTEM_USER_ID
        assert attr.updated_at == merge_at
        assert attr.updated_by == "branch-user-delete"

    # Validate deleted car's relationships metadata
    for rel in deleted_car_meta.relationships:
        assert rel.is_deleted is True
        assert rel.created_at == e_car_2_created_at
        assert rel.created_by == SYSTEM_USER_ID
        assert rel.updated_at == merge_at
        assert rel.updated_by == "branch-user-delete"

    await verify_graph(db=db)

    await diff_merger.rollback(at=merge_at)

    rolled_back_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    registry.schema.set_schema_branch(name=default_branch.name, schema=rolled_back_schema_branch)
    car_schema_main = rolled_back_schema_branch.get(name="TestElectricCar", duplicate=False)
    assert "TestVehicle" not in car_schema_main.inherit_from
    with pytest.raises(SchemaNotFoundError):
        rolled_back_schema_branch.get(name="Test2NewElectricCar", duplicate=False)
    retrieved_unmigrated_car = await NodeManager.get_one(db=db, branch=default_branch, id=e_car_1.id)
    assert retrieved_unmigrated_car.get_kind() == "TestElectricCar"
    assert retrieved_unmigrated_car.color.value == e_car_1.color.value
    retrieved_owner_rels = await retrieved_unmigrated_car.owner.get_relationships(db=db)
    assert {r.get_peer_id() for r in retrieved_owner_rels} == {original_e_car_1_owner.id}
    with pytest.raises(SchemaNotFoundError):
        await NodeManager.query(db=db, branch=default_branch, schema="Test2NewElectricCar")
    # get undeleted node
    undeleted_car = await NodeManager.get_one(db=db, branch=default_branch, id=e_car_2.id)
    assert undeleted_car.get_kind() == "TestElectricCar"

    # Validate node-level metadata after rollback for e_car_1
    rolled_back_car_with_metadata = await NodeManager.get_one(
        db=db,
        branch=default_branch,
        id=e_car_1.id,
        include_metadata=MetadataQueryOptions(
            node_level=MetadataOptions.USER_TIMESTAMPS,
            attribute_level=MetadataOptions.USER_TIMESTAMPS,
            relationship_level=MetadataOptions.USER_TIMESTAMPS,
        ),
        prefetch_relationships=True,
    )
    # After rollback, should have original created_at and no user updates
    assert rolled_back_car_with_metadata._get_created_at() == e_car_1_created_at
    assert rolled_back_car_with_metadata._get_created_by() == SYSTEM_USER_ID
    assert rolled_back_car_with_metadata._get_updated_at() == e_car_1_created_at
    assert rolled_back_car_with_metadata._get_updated_by() == SYSTEM_USER_ID

    # Validate attribute-level metadata after rollback
    assert rolled_back_car_with_metadata.color._get_created_at() == e_car_1_created_at
    assert rolled_back_car_with_metadata.color._get_created_by() == SYSTEM_USER_ID
    assert rolled_back_car_with_metadata.color._get_updated_at() == e_car_1_created_at
    assert rolled_back_car_with_metadata.color._get_updated_by() == SYSTEM_USER_ID

    assert rolled_back_car_with_metadata.name._get_created_at() == e_car_1_created_at
    assert rolled_back_car_with_metadata.name._get_created_by() == SYSTEM_USER_ID
    assert rolled_back_car_with_metadata.name._get_updated_at() == e_car_1_created_at
    assert rolled_back_car_with_metadata.name._get_updated_by() == SYSTEM_USER_ID

    # Validate relationship-level metadata after rollback for e_car_1
    # After rollback, owner relationship should have original timestamps restored
    owner_rel_manager = rolled_back_car_with_metadata.get_relationship(name="owner")
    owner_rel = await owner_rel_manager.get(db=db)
    assert owner_rel._get_created_at() == e_car_1_created_at
    assert owner_rel._get_created_by() == SYSTEM_USER_ID
    assert owner_rel._get_updated_at() == e_car_1_created_at
    assert owner_rel._get_updated_by() == SYSTEM_USER_ID

    # Validate undeleted car (e_car_2) metadata after rollback
    undeleted_car_with_metadata = await NodeManager.get_one(
        db=db,
        branch=default_branch,
        id=e_car_2.id,
        include_metadata=MetadataQueryOptions(
            node_level=MetadataOptions.USER_TIMESTAMPS,
            attribute_level=MetadataOptions.USER_TIMESTAMPS,
            relationship_level=MetadataOptions.USER_TIMESTAMPS,
        ),
        prefetch_relationships=True,
    )
    # Should have original timestamps restored
    assert undeleted_car_with_metadata._get_created_at() == e_car_2_created_at
    assert undeleted_car_with_metadata._get_created_by() == SYSTEM_USER_ID
    assert undeleted_car_with_metadata._get_updated_at() == e_car_2_created_at
    assert undeleted_car_with_metadata._get_updated_by() == SYSTEM_USER_ID

    # Validate attribute metadata on undeleted car
    assert undeleted_car_with_metadata.color._get_created_at() == e_car_2_created_at
    assert undeleted_car_with_metadata.color._get_created_by() == SYSTEM_USER_ID
    assert undeleted_car_with_metadata.color._get_updated_at() == e_car_2_created_at
    assert undeleted_car_with_metadata.color._get_updated_by() == SYSTEM_USER_ID

    # Validate relationship metadata on undeleted car after rollback
    owner_rel_manager = undeleted_car_with_metadata.get_relationship(name="owner")
    owner_rel = await owner_rel_manager.get(db=db)
    assert owner_rel._get_created_at() == e_car_2_created_at
    assert owner_rel._get_created_by() == SYSTEM_USER_ID
    assert owner_rel._get_updated_at() == e_car_2_created_at
    assert owner_rel._get_updated_by() == SYSTEM_USER_ID
