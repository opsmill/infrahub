import uuid
from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SYSTEM_USER_ID, MetadataOptions, SchemaPathType
from infrahub.core.initialization import (
    create_branch,
)
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.migrations.schema.attribute_name_update import (
    AttributeNameUpdateMigration,
    AttributeNameUpdateMigrationQuery01,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.query.rollback import RollbackQuery, RollbackScope
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.definitions.core.template import core_object_template
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase
from tests.component.core.migrations.schema.metadata_helpers import (
    VertexMetadata,
    branch_edge_fingerprint,
    branch_metadata_fingerprint,
    get_attribute_vertex_metadata,
    get_node_vertex_metadata,
)
from tests.db_snapshot import DbSnapshotter
from tests.helpers.db_validation import verify_graph
from tests.helpers.edge_timestamps import assert_edge_timestamps


@pytest.fixture
async def car_person_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> SchemaBranch:
    registry.schema.register_schema(schema=SchemaRoot(generics=[core_object_template]), branch=default_branch.name)
    for node in car_person_schema_unregistered.nodes:
        node.generate_template = True
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


async def test_query_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node, car_profile1_main: Node
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="color")
    prev_attr.id = str(uuid.uuid4())
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="color")
    new_attr.name = "new-color"
    new_attr.id = prev_attr.id

    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    migration = AttributeNameUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="new-color"),
    )
    query = await AttributeNameUpdateMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)

    assert query.get_nbr_migrations_executed() == 3

    # We expect 9 more relationships because there are 3 attributes with 3 relationships each
    assert await count_relationships(db=db) == count_rels + 9
    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 3

    # Re-execute the query once to ensure that it won't change anything
    query = await AttributeNameUpdateMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0

    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 3
    assert await count_relationships(db=db) == count_rels + 9


async def test_query_branch1(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node, car_profile1_main: Node
) -> None:
    branch1 = await create_branch(db=db, branch_name="branch1", isolated=True)

    schema = registry.schema.get_schema_branch(name=branch1.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="color")
    prev_attr.id = str(uuid.uuid4())
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="color")
    new_attr.name = "new-color"
    new_attr.id = prev_attr.id

    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    migration = AttributeNameUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="new-color"),
    )
    query = await AttributeNameUpdateMigrationQuery01.init(db=db, branch=branch1, migration=migration)

    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 3

    # We expect 18 more relationships because there are 3 attributes with 6 relationships each
    assert await count_relationships(db=db) == count_rels + 18
    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 3

    # Re-execute the query once to ensure that it won't change anything
    query = await AttributeNameUpdateMigrationQuery01.init(db=db, branch=branch1, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0

    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 3
    assert await count_relationships(db=db) == count_rels + 18


async def test_migration(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node, car_profile1_main: Node
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

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="color")
    prev_attr.id = str(uuid.uuid4())
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="color")
    new_attr.name = "new-color"
    new_attr.id = prev_attr.id

    # 1. Snapshot before migration
    snapshotter = DbSnapshotter(db)
    before_snapshot = await snapshotter.snapshot()

    # 2. Count nodes and relationships before migration
    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    # 3. Create explicit timestamp
    at = Timestamp()
    at_str = at.to_string()

    # 4. Execute migration
    migration = AttributeNameUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="new-color"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=default_branch)
    assert not execution_result.errors
    # 2 TestCar + 1 ProfileTestCar + 2 TemplateTestCar = 5 migrations
    assert execution_result.nbr_migrations_executed == 5

    # 5. Validate nodes and relationships after migration
    # 5 new Attribute nodes (one per renamed attribute), 5 x 3 = 15 new relationships
    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 5
    assert await count_relationships(db=db) == count_rels + 15

    # 6. Validate edge timestamps
    after_snapshot = await snapshotter.snapshot()
    assert_edge_timestamps(before_snapshot, after_snapshot, at_str)


@dataclass
class _AttributeRename:
    """State captured around a single ``color`` -> ``new_color`` rename migration on one branch."""

    branch: Branch
    node_id: str
    migration_time: Timestamp
    user_id: str
    node_before: VertexMetadata
    pre_migration_fingerprint: list[tuple]
    pre_migration_metadata: list[tuple]


async def _run_attribute_rename_migration(db: InfrahubDatabase, branch: Branch, node_uuid: str) -> _AttributeRename:
    """Run the ``color`` -> ``new_color`` rename migration on ``branch`` and capture the surrounding state.

    Captures the pre-migration Node vertex metadata and branch edge fingerprint so callers can assert the
    snapshot (default/global branch) and a rollback's restore. The renamed attribute vertex does not exist
    before the migration, so only the pre-existing Node is snapshotted here.
    """
    node_before = await get_node_vertex_metadata(db=db, node_uuid=node_uuid)
    pre_migration_fingerprint = await branch_edge_fingerprint(db=db, branch_name=branch.name)
    pre_migration_metadata = await branch_metadata_fingerprint(db=db, branch_name=branch.name)

    user_id = "migration_user"
    migration_time = Timestamp()

    schema = registry.schema.get_schema_branch(name=branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="color")
    prev_attr.id = str(uuid.uuid4())
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="color")
    new_attr.name = "new_color"
    new_attr.id = prev_attr.id

    migration = AttributeNameUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="new_color"),
    )
    execution_result = await migration.execute(
        migration_input=MigrationInput(db=db, at=migration_time, user_id=user_id), branch=branch
    )
    assert not execution_result.errors

    # Reflect the rename in the in-place branch schema so the ORM can resolve the ``new_color`` field.
    car_schema = schema.get(name="TestCar", duplicate=False)
    car_schema.get_attribute(name="color").name = "new_color"

    return _AttributeRename(
        branch=branch,
        node_id=node_uuid,
        migration_time=migration_time,
        user_id=user_id,
        node_before=node_before,
        pre_migration_fingerprint=pre_migration_fingerprint,
        pre_migration_metadata=pre_migration_metadata,
    )


async def _assert_migration_metadata(db: InfrahubDatabase, context: _AttributeRename) -> None:
    """Assert the rename's metadata effect, which differs by branch.

    On every branch the change is reflected through the edges (the new HAS_ATTRIBUTE edge and the ORM's
    edge-derived timestamps). Vertex-level metadata is maintained only on the default/global branch, so
    only there does the rename bump ``updated_at``/``by`` on the Node and set it on the freshly-created
    ``new_color`` Attribute; on a user branch the shared Node vertex is left untouched.
    """
    updated_car = await NodeManager.get_one(
        db=db,
        branch=context.branch,
        id=context.node_id,
        include_metadata=MetadataQueryOptions(
            node_level=MetadataOptions.USER_TIMESTAMPS, attribute_level=MetadataOptions.USER_TIMESTAMPS
        ),
        fields={"new_color": True},
    )
    assert updated_car._get_created_at() < context.migration_time
    assert updated_car._get_created_by() == SYSTEM_USER_ID
    assert updated_car._get_updated_at() == context.migration_time
    assert updated_car._get_updated_by() == context.user_id

    new_color_attr = updated_car.get_attribute("new_color")
    assert new_color_attr._get_created_at() == context.migration_time
    assert new_color_attr._get_created_by() == context.user_id
    assert new_color_attr._get_updated_at() == context.migration_time
    assert new_color_attr._get_updated_by() == context.user_id

    node_after = await get_node_vertex_metadata(db=db, node_uuid=context.node_id)
    if context.branch.is_default or context.branch.is_global:
        # The bump snapshots the pre-migration Node values so a merge-failure rollback can restore them.
        assert node_after.updated_at == context.migration_time.to_string()
        assert node_after.updated_by == context.user_id
        assert node_after.previous_updated_at == context.node_before.updated_at
        assert node_after.previous_updated_by == context.node_before.updated_by
        # The renamed Attribute vertex is created by this migration, so its metadata is set to the
        # migration timestamp but there is no prior value to snapshot into previous_*.
        new_color_after = await get_attribute_vertex_metadata(
            db=db, node_uuid=context.node_id, attribute_name="new_color", edge_from=context.migration_time.to_string()
        )
        assert new_color_after.updated_at == context.migration_time.to_string()
        assert new_color_after.updated_by == context.user_id
        assert new_color_after.previous_updated_at is None
    else:
        # A user-branch migration leaves the shared Node vertex untouched and records no snapshot.
        assert node_after == context.node_before
        assert node_after.previous_updated_at is None


class TestAttributeNameUpdateMetadata:
    """On the default branch, renaming an attribute snapshots Node metadata and a rollback restores it.

    A class-scoped fixture runs the migration once; the metadata and rollback tests share it and run in
    order (the rollback test reverts the state the metadata test observed).
    """

    @pytest.fixture(scope="class")
    async def rename(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
        car_person_schema_scope_class: SchemaBranch,
    ) -> _AttributeRename:
        person = await Node.init(db=db, schema="TestPerson", branch=default_branch_scope_class)
        await person.new(db=db, name="John", height=180)
        await person.save(db=db)
        car = await Node.init(db=db, schema="TestCar", branch=default_branch_scope_class)
        await car.new(db=db, name="accord", color="#123456", owner=person.id)
        await car.save(db=db)

        return await _run_attribute_rename_migration(db=db, branch=default_branch_scope_class, node_uuid=car.id)

    async def test_migration_metadata(self, db: InfrahubDatabase, rename: _AttributeRename) -> None:
        """The rename bumps updated_at/by on the Node, snapshots its prior values, and sets the new vertex."""
        await _assert_migration_metadata(db=db, context=rename)

    async def test_migration_rollback(self, db: InfrahubDatabase, rename: _AttributeRename) -> None:
        """RollbackQuery undoes the migration: the branch edges and Node metadata are restored, idempotently."""

        async def _run_rollback() -> None:
            query = await RollbackQuery.init(
                db=db,
                target_branch=rename.branch,
                at=rename.migration_time,
                scope=RollbackScope.SINCE_TIMESTAMP,
                restore_metadata=True,
            )
            await query.execute(db=db)

        await _run_rollback()
        await verify_graph(db=db)

        # The branch edges are restored exactly to their pre-migration state.
        assert await branch_edge_fingerprint(db=db, branch_name=rename.branch.name) == rename.pre_migration_fingerprint
        assert await branch_metadata_fingerprint(db=db, branch_name=rename.branch.name) == rename.pre_migration_metadata

        # The Node metadata is restored to its pre-migration values and the snapshot is cleared. The
        # freshly-created new_color Attribute vertex is deleted by the rollback rather than restored.
        node_after = await get_node_vertex_metadata(db=db, node_uuid=rename.node_id)
        assert node_after.updated_at == rename.node_before.updated_at
        assert node_after.updated_by == rename.node_before.updated_by
        assert node_after.previous_updated_at is None
        assert node_after.previous_updated_by is None

        # Running the rollback again is a no-op: nothing remains in the window to revert.
        await _run_rollback()
        await verify_graph(db=db)
        assert await branch_edge_fingerprint(db=db, branch_name=rename.branch.name) == rename.pre_migration_fingerprint
        assert await branch_metadata_fingerprint(db=db, branch_name=rename.branch.name) == rename.pre_migration_metadata
        node_again = await get_node_vertex_metadata(db=db, node_uuid=rename.node_id)
        assert node_again == node_after


async def test_migration_metadata_non_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node
) -> None:
    """On a user branch the rename is reflected through edges but records no Node vertex-metadata snapshot."""
    branch = await create_branch(branch_name="branch-attr-rename", db=db)
    context = await _run_attribute_rename_migration(db=db, branch=branch, node_uuid=car_accord_main.id)
    await _assert_migration_metadata(db=db, context=context)
