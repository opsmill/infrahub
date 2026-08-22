from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SYSTEM_USER_ID, HashableModelState, MetadataOptions, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.migrations.schema.node_attribute_remove import (
    NodeAttributeRemoveMigration,
    NodeAttributeRemoveMigrationQuery01,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.query.rollback import RollbackScope
from infrahub.core.rollback import GraphRollbacker
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
)
from tests.db_snapshot import DbSnapshotter
from tests.helpers.db_validation import verify_graph
from tests.helpers.edge_timestamps import assert_edge_timestamps


async def _get_car_and_color_metadata(db: InfrahubDatabase, node_uuid: str) -> tuple[VertexMetadata, VertexMetadata]:
    """Return the vertex metadata for a TestCar node and its ``color`` attribute.

    The HAS_ATTRIBUTE edge is traversed regardless of its status, so this works both before the
    removal (edge active) and after it (edge closed).
    """
    query = """
        MATCH (n:TestCar {uuid: $node_uuid})-[:HAS_ATTRIBUTE]->(a:Attribute {name: "color"})
        RETURN n.updated_at AS node_updated_at, n.updated_by AS node_updated_by,
            n.previous_updated_at AS node_previous_updated_at, n.previous_updated_by AS node_previous_updated_by,
            a.updated_at AS attr_updated_at, a.updated_by AS attr_updated_by,
            a.previous_updated_at AS attr_previous_updated_at, a.previous_updated_by AS attr_previous_updated_by
    """
    results = await db.execute_query(
        query=query,
        params={"node_uuid": node_uuid},
    )
    row = results[0]
    node_metadata = VertexMetadata(
        updated_at=row["node_updated_at"],
        updated_by=row["node_updated_by"],
        previous_updated_at=row["node_previous_updated_at"],
        previous_updated_by=row["node_previous_updated_by"],
    )
    attr_metadata = VertexMetadata(
        updated_at=row["attr_updated_at"],
        updated_by=row["attr_updated_by"],
        previous_updated_at=row["attr_previous_updated_at"],
        previous_updated_by=row["attr_previous_updated_by"],
    )
    return node_metadata, attr_metadata


@pytest.fixture
async def car_person_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> SchemaBranch:
    registry.schema.register_schema(schema=SchemaRoot(generics=[core_object_template]), branch=default_branch.name)
    for node in car_person_schema_unregistered.nodes:
        node.generate_template = True
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


async def test_query_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    attr = car_schema.get_attribute(name="color")
    attr.state = HashableModelState.ABSENT

    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    migration = NodeAttributeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    query = await NodeAttributeRemoveMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 2

    # We expect 6 more relationships because there are 2 attributes with 3 relationships each
    assert await count_relationships(db=db) == count_rels + 6
    assert await count_nodes(db=db, label="Attribute") == count_attr_node

    # Re-execute the query once to ensure that it won't change anything
    query = await NodeAttributeRemoveMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0
    assert await count_nodes(db=db, label="Attribute") == count_attr_node
    assert await count_relationships(db=db) == count_rels + 6


async def test_query_default_branch_generic_with_override(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics_unregistered: dict[str, Any]
) -> None:
    for node_schema_dict in car_person_schema_generics_unregistered["nodes"]:
        if node_schema_dict["name"] == "ElectricCar":
            node_schema_dict["attributes"].append(
                {"name": "color", "kind": "Text", "default_value": "#555555", "max_length": 8}
            )
    schema_root = SchemaRoot(**car_person_schema_generics_unregistered)
    schema = registry.schema.register_schema(schema=schema_root, branch=default_branch.name)

    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)
    p2 = await Node.init(db=db, schema="TestPerson")
    await p2.new(db=db, name="Jane", height=170)
    await p2.save(db=db)
    e_car = await Node.init(db=db, schema="TestElectricCar")
    await e_car.new(db=db, name="volt", nbr_seats=3, nbr_engine=4, owner=p1, color="#aaabbbc")
    await e_car.save(db=db)
    g_car = await Node.init(db=db, schema="TestGazCar")
    await g_car.new(db=db, name="nolt", nbr_seats=4, mpg=25, owner=p2)
    await g_car.save(db=db)

    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    attr = car_schema.get_attribute(name="color")
    attr.state = HashableModelState.ABSENT

    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    migration = NodeAttributeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    query = await NodeAttributeRemoveMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 1

    # We expect 6 more relationships because there are 2 attributes with 3 relationships each
    assert await count_relationships(db=db) == count_rels + 3
    assert await count_nodes(db=db, label="Attribute") == count_attr_node

    # Re-execute the query once to ensure that it won't change anything
    query = await NodeAttributeRemoveMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0
    assert await count_nodes(db=db, label="Attribute") == count_attr_node
    assert await count_relationships(db=db) == count_rels + 3


async def test_migration(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
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
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    attr = car_schema.get_attribute(name="color")
    attr.state = HashableModelState.ABSENT

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
    migration = NodeAttributeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=default_branch)
    assert not execution_result.errors
    # 2 TestCar + 2 TemplateTestCar = 4 migrations
    assert execution_result.nbr_migrations_executed == 4

    # 5. Validate nodes and relationships after migration
    # 4 attributes x 3 relationships each = 12 new deleted edges
    assert await count_nodes(db=db, label="Attribute") == count_attr_node
    assert await count_relationships(db=db) == count_rels + 12

    # 6. Validate edge timestamps
    after_snapshot = await snapshotter.snapshot()
    assert_edge_timestamps(before_snapshot, after_snapshot, at_str)


@dataclass
class _AttributeRemoval:
    """State captured around a single ``color`` attribute-removal migration on one branch."""

    branch: Branch
    node_id: str
    migration_time: Timestamp
    user_id: str
    node_before: VertexMetadata
    attr_before: VertexMetadata
    pre_migration_fingerprint: list[tuple]
    pre_migration_metadata: list[tuple]


async def _run_removal_migration(db: InfrahubDatabase, branch: Branch, node_uuid: str) -> _AttributeRemoval:
    """Run the ``color``-attribute removal migration on ``branch`` and capture the surrounding state.

    Captures the pre-migration vertex metadata and branch edge fingerprint so callers can assert the
    snapshot (default/global branch) and a rollback's restore.
    """
    node_before, attr_before = await _get_car_and_color_metadata(db=db, node_uuid=node_uuid)
    pre_migration_fingerprint = await branch_edge_fingerprint(db=db, branch_name=branch.name)
    pre_migration_metadata = await branch_metadata_fingerprint(db=db, branch_name=branch.name)

    user_id = "test-metadata-user"
    migration_time = Timestamp()

    schema = registry.schema.get_schema_branch(name=branch.name)
    candidate_schema = schema.duplicate()
    candidate_schema.get(name="TestCar").get_attribute(name="color").state = HashableModelState.ABSENT

    migration = NodeAttributeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=candidate_schema.get(name="TestCar"),
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    execution_result = await migration.execute(
        migration_input=MigrationInput(db=db, at=migration_time, user_id=user_id), branch=branch
    )
    assert not execution_result.errors

    return _AttributeRemoval(
        branch=branch,
        node_id=node_uuid,
        migration_time=migration_time,
        user_id=user_id,
        node_before=node_before,
        attr_before=attr_before,
        pre_migration_fingerprint=pre_migration_fingerprint,
        pre_migration_metadata=pre_migration_metadata,
    )


async def _assert_migration_metadata(db: InfrahubDatabase, removal: _AttributeRemoval) -> None:
    """Assert the removal's metadata effect, which differs by branch.

    On every branch the change is reflected through the edges (the closed HAS_ATTRIBUTE edge and the
    ORM's edge-derived timestamps). Vertex-level metadata is maintained only on the default/global
    branch, so only there does the removal bump ``updated_at``/``by`` on the vertices and snapshot the
    prior values into ``previous_*``; on a user branch the shared vertices are left untouched.
    """
    updated_car = await NodeManager.get_one(
        db=db,
        branch=removal.branch,
        id=removal.node_id,
        include_metadata=MetadataQueryOptions(node_level=MetadataOptions.USER_TIMESTAMPS),
        fields={"color": True},
    )
    assert updated_car._get_created_at() < removal.migration_time
    assert updated_car._get_created_by() == SYSTEM_USER_ID
    assert updated_car._get_updated_at() == removal.migration_time
    assert updated_car._get_updated_by() == removal.user_id

    # The removal closes the HAS_ATTRIBUTE edge with the migration's user/timestamp.
    edge_results = await db.execute_query(
        query="""
        MATCH (:TestCar {uuid: $node_uuid})-[r:HAS_ATTRIBUTE {branch: $branch, status: "deleted"}]->(:Attribute {name: "color"})
        RETURN r.from_user_id as from_user_id, r.from as from_time
        """,
        params={"node_uuid": removal.node_id, "branch": removal.branch.name},
    )
    assert len(edge_results) > 0, "Expected at least one deleted HAS_ATTRIBUTE edge"
    assert edge_results[0]["from_user_id"] == removal.user_id
    assert edge_results[0]["from_time"] == removal.migration_time.to_string()

    node_after, attr_after = await _get_car_and_color_metadata(db=db, node_uuid=removal.node_id)
    if removal.branch.is_default or removal.branch.is_global:
        # The bump snapshots the pre-migration values so a merge-failure rollback can restore them. The
        # Attribute vertex being removed is pre-existing and survives a rollback, so it too needs a snapshot.
        assert node_after.updated_at == removal.migration_time.to_string()
        assert node_after.updated_by == removal.user_id
        assert node_after.previous_updated_at == removal.node_before.updated_at
        assert node_after.previous_updated_by == removal.node_before.updated_by
        assert attr_after.updated_at == removal.migration_time.to_string()
        assert attr_after.updated_by == removal.user_id
        assert attr_after.previous_updated_at == removal.attr_before.updated_at
        assert attr_after.previous_updated_by == removal.attr_before.updated_by
    else:
        # A user-branch migration leaves the shared vertices untouched and records no snapshot.
        assert node_after == removal.node_before
        assert attr_after == removal.attr_before
        assert node_after.previous_updated_at is None
        assert attr_after.previous_updated_at is None


class TestAttributeRemoveMetadata:
    """On the default branch, removing an attribute snapshots vertex metadata and a rollback restores it.

    A class-scoped fixture runs the migration once; the metadata and rollback tests share it and run in
    order (the rollback test reverts the state the metadata test observed).
    """

    @pytest.fixture(scope="class")
    async def removal(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
        car_person_schema_scope_class: SchemaBranch,
    ) -> _AttributeRemoval:
        person = await Node.init(db=db, schema="TestPerson", branch=default_branch_scope_class)
        await person.new(db=db, name="John", height=180)
        await person.save(db=db)
        car = await Node.init(db=db, schema="TestCar", branch=default_branch_scope_class)
        await car.new(db=db, name="accord", color="#123456", owner=person.id)
        await car.save(db=db)

        return await _run_removal_migration(db=db, branch=default_branch_scope_class, node_uuid=car.id)

    async def test_migration_metadata(self, db: InfrahubDatabase, removal: _AttributeRemoval) -> None:
        """The removal bumps updated_at/by on the Node and Attribute and snapshots the prior values."""
        await _assert_migration_metadata(db=db, removal=removal)

    async def test_migration_rollback(self, db: InfrahubDatabase, removal: _AttributeRemoval) -> None:
        """A range rollback undoes the migration: the branch edges and vertex metadata are restored, idempotently."""

        async def _run_rollback() -> None:
            await GraphRollbacker(db=db).rollback(
                target_branch=removal.branch,
                at=removal.migration_time,
                scope=RollbackScope.SINCE_TIMESTAMP,
            )

        await _run_rollback()
        await verify_graph(db=db)

        # The branch edges are restored exactly to their pre-migration state.
        assert (
            await branch_edge_fingerprint(db=db, branch_name=removal.branch.name) == removal.pre_migration_fingerprint
        )
        assert (
            await branch_metadata_fingerprint(db=db, branch_name=removal.branch.name) == removal.pre_migration_metadata
        )

        # The vertex metadata is restored to its pre-migration values and the snapshot is cleared.
        node_after, attr_after = await _get_car_and_color_metadata(db=db, node_uuid=removal.node_id)
        assert node_after.updated_at == removal.node_before.updated_at
        assert node_after.updated_by == removal.node_before.updated_by
        assert node_after.previous_updated_at is None
        assert node_after.previous_updated_by is None
        assert attr_after.updated_at == removal.attr_before.updated_at
        assert attr_after.updated_by == removal.attr_before.updated_by
        assert attr_after.previous_updated_at is None
        assert attr_after.previous_updated_by is None

        # Running the rollback again is a no-op: nothing remains in the window to revert.
        await _run_rollback()
        await verify_graph(db=db)
        assert (
            await branch_edge_fingerprint(db=db, branch_name=removal.branch.name) == removal.pre_migration_fingerprint
        )
        assert (
            await branch_metadata_fingerprint(db=db, branch_name=removal.branch.name) == removal.pre_migration_metadata
        )
        node_again, attr_again = await _get_car_and_color_metadata(db=db, node_uuid=removal.node_id)
        assert node_again == node_after
        assert attr_again == attr_after


async def test_migration_metadata_non_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node
) -> None:
    """On a user branch the removal is reflected through edges but records no vertex-metadata snapshot."""
    branch = await create_branch(branch_name="branch-attr-remove", db=db)
    removal = await _run_removal_migration(db=db, branch=branch, node_uuid=car_accord_main.id)
    await _assert_migration_metadata(db=db, removal=removal)
