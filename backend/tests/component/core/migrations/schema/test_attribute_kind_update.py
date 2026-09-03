from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.schema.attribute_kind_update import (
    AttributeKindUpdateMigration,
    AttributeKindUpdateMigrationQuery,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.query.rollback import RollbackScope
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_graph
from tests.db_snapshot import DbSnapshotter
from tests.helpers.edge_timestamps import assert_edge_timestamps
from tests.helpers.schema import load_schema
from tests.helpers.vertex_metadata import (
    VertexMetadata,
    branch_edge_fingerprint,
    branch_metadata_fingerprint,
)

CAR_SCHEMA_TEXT = {
    "version": "1.0",
    "nodes": [
        {
            "name": "Car",
            "namespace": "Test",
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "description", "kind": "Text"},  # Text is indexed
            ],
        }
    ],
}


async def _get_car_and_description_metadata(
    db: InfrahubDatabase, node_uuid: str
) -> tuple[VertexMetadata, VertexMetadata]:
    """Return the vertex metadata for a TestCar node and its ``description`` attribute.

    The kind-update migration reuses the existing Attribute vertex rather than creating a new one, so
    the ``description`` Attribute is reachable regardless of whether the migration has run yet.
    """
    query = """
        MATCH (n:TestCar {uuid: $node_uuid})-[:HAS_ATTRIBUTE]->(a:Attribute {name: "description"})
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


async def check_attribute_value_vertices(db: InfrahubDatabase, value: str) -> tuple[int, int]:
    """Return number of indexed and non-indexed AttributeValue vertices for a given value."""
    query = "MATCH (av:AttributeValue) WHERE av.value = $value RETURN 'AttributeValueIndexed' IN labels(av) AS is_indexed, count(av) AS num_vertices"
    results = await db.execute_query(query=query, params={"value": value})
    num_indexed, num_non_indexed = 0, 0
    for result in results:
        if result["is_indexed"]:
            num_indexed = result["num_vertices"]
        else:
            num_non_indexed = result["num_vertices"]
    return num_indexed, num_non_indexed


async def test_query_indexed_to_not_indexed(db: InfrahubDatabase, default_branch: Branch) -> None:
    """Test changing attribute kind from indexed (Text) to not indexed (TextArea)."""
    await load_schema(db=db, schema=SchemaRoot(**CAR_SCHEMA_TEXT))
    description = "A nice car"

    car = await Node.init(db=db, schema="TestCar")
    await car.new(db=db, name="Accord", description=description)
    await car.save(db=db)

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    # Change description from Text (indexed) to TextArea (not indexed)
    new_attr = new_car_schema.get_attribute(name="description")
    new_attr.kind = "TextArea"

    # check that only 1 "A nice car" AttributeValue vertex exists
    num_indexed, num_non_indexed = await check_attribute_value_vertices(db=db, value=description)
    assert num_indexed == 1
    assert num_non_indexed == 0

    migration = AttributeKindUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="description"),
    )
    query = await AttributeKindUpdateMigrationQuery.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)

    # Re-execute the query once to ensure that it won't change anything
    query = await AttributeKindUpdateMigrationQuery.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)

    # check that a non-indexed "A nice car" AttributeValue vertex was created
    num_indexed, num_non_indexed = await check_attribute_value_vertices(db=db, value=description)
    assert num_indexed == 1
    assert num_non_indexed == 1


async def test_migration_no_change_when_same_index_status(db: InfrahubDatabase, default_branch: Branch) -> None:
    """Test that migration does nothing when attribute indexing status doesn't change."""
    await load_schema(db=db, schema=SchemaRoot(**CAR_SCHEMA_TEXT))

    car = await Node.init(db=db, schema="TestCar")
    await car.new(db=db, name="Accord", description="A nice car")
    await car.save(db=db)

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    # Change description from Text to another indexed type (e.g., Number)
    new_attr = new_car_schema.get_attribute(name="description")
    new_attr.kind = "Number"

    migration = AttributeKindUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="description"),
    )

    # Migration should return early without executing any queries
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 0


async def test_migration_edge_timestamps(db: InfrahubDatabase, default_branch: Branch) -> None:
    """Verify edges created/modified during AttributeKindUpdateMigration use the 'at' timestamp."""
    await load_schema(db=db, schema=SchemaRoot(**CAR_SCHEMA_TEXT))

    car = await Node.init(db=db, schema="TestCar")
    await car.new(db=db, name="Accord", description="A nice car")
    await car.save(db=db)

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    # Change description from Text (indexed) to TextArea (not indexed)
    new_attr = new_car_schema.get_attribute(name="description")
    new_attr.kind = "TextArea"

    # 1. Snapshot before migration
    snapshotter = DbSnapshotter(db)
    before_snapshot = await snapshotter.snapshot()

    # 2. Create explicit timestamp
    at = Timestamp()
    at_str = at.to_string()

    # 3. Execute migration
    migration = AttributeKindUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="description"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=default_branch)
    assert not execution_result.errors

    # 4. Validate edge timestamps
    after_snapshot = await snapshotter.snapshot()
    assert_edge_timestamps(before_snapshot, after_snapshot, at_str)


@dataclass
class _AttributeKindUpdate:
    """State captured around a single ``description`` kind-update migration on one branch."""

    branch: Branch
    node_id: str
    migration_time: Timestamp
    user_id: str
    node_before: VertexMetadata
    attr_before: VertexMetadata
    pre_migration_fingerprint: list[tuple]
    pre_migration_metadata: list[tuple]


async def _run_kind_update_migration(db: InfrahubDatabase, branch: Branch, node_uuid: str) -> _AttributeKindUpdate:
    """Run the ``description`` Text->TextArea kind-update migration on ``branch`` and capture the surrounding state.

    Captures the pre-migration vertex metadata and branch edge fingerprint so callers can assert the
    snapshot (default/global branch) and a rollback's restore.
    """
    node_before, attr_before = await _get_car_and_description_metadata(db=db, node_uuid=node_uuid)
    pre_migration_fingerprint = await branch_edge_fingerprint(db=db, branch_name=branch.name)
    pre_migration_metadata = await branch_metadata_fingerprint(db=db, branch_name=branch.name)

    user_id = "migration_user"
    migration_time = Timestamp()

    schema = registry.schema.get_schema_branch(name=branch.name)
    prev_car_schema = schema.get(name="TestCar")
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    # Change description from Text (indexed) to TextArea (not indexed) so the migration runs.
    new_car_schema.get_attribute(name="description").kind = "TextArea"

    migration = AttributeKindUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="description"),
    )
    execution_result = await migration.execute(
        migration_input=MigrationInput(db=db, at=migration_time, user_id=user_id), branch=branch
    )
    assert not execution_result.errors

    return _AttributeKindUpdate(
        branch=branch,
        node_id=node_uuid,
        migration_time=migration_time,
        user_id=user_id,
        node_before=node_before,
        attr_before=attr_before,
        pre_migration_fingerprint=pre_migration_fingerprint,
        pre_migration_metadata=pre_migration_metadata,
    )


async def _assert_migration_metadata(db: InfrahubDatabase, update: _AttributeKindUpdate) -> None:
    """Assert the kind update's metadata effect, which differs by branch.

    On every branch the change is reflected through the edges: a new active non-indexed HAS_VALUE edge
    is written with the migration's user/timestamp. Vertex-level metadata is maintained only on the
    default/global branch, so only there does the migration bump ``updated_at``/``by`` on the reused
    Attribute and its Node and snapshot the prior values into ``previous_*``; on a user branch the
    shared vertices are left untouched.
    """
    # The migration writes a new active HAS_VALUE edge to a non-indexed AttributeValue on the branch.
    edge_results = await db.execute_query(
        query="""
        MATCH (:TestCar {uuid: $node_uuid})-[:HAS_ATTRIBUTE]->(a:Attribute {name: "description"})
        MATCH (a)-[r:HAS_VALUE {branch: $branch, status: "active"}]->(av:AttributeValue)
        WHERE r.from = $at AND r.to IS NULL
        RETURN r.from_user_id AS from_user_id, r.from AS from_time,
            "AttributeValueIndexed" IN labels(av) AS is_indexed
        """,
        params={"node_uuid": update.node_id, "branch": update.branch.name, "at": update.migration_time.to_string()},
    )
    assert len(edge_results) == 1, "Expected at least one new active HAS_VALUE edge"
    assert edge_results[0]["from_user_id"] == update.user_id
    assert edge_results[0]["from_time"] == update.migration_time.to_string()
    assert edge_results[0]["is_indexed"] is False

    node_after, attr_after = await _get_car_and_description_metadata(db=db, node_uuid=update.node_id)
    if update.branch.is_default or update.branch.is_global:
        # The bump snapshots the pre-migration values so a merge-failure rollback can restore them. The
        # Attribute vertex is reused (not recreated) and survives a rollback, so it too needs a snapshot.
        assert node_after.updated_at == update.migration_time.to_string()
        assert node_after.updated_by == update.user_id
        assert node_after.previous_updated_at == update.node_before.updated_at
        assert node_after.previous_updated_by == update.node_before.updated_by
        assert attr_after.updated_at == update.migration_time.to_string()
        assert attr_after.updated_by == update.user_id
        assert attr_after.previous_updated_at == update.attr_before.updated_at
        assert attr_after.previous_updated_by == update.attr_before.updated_by
    else:
        # A user-branch migration leaves the shared vertices untouched and records no snapshot.
        assert node_after == update.node_before
        assert attr_after == update.attr_before
        assert node_after.previous_updated_at is None
        assert attr_after.previous_updated_at is None


class TestAttributeKindUpdateMetadata:
    """On the default branch, a kind update snapshots vertex metadata and a rollback restores it.

    A class-scoped fixture runs the migration once; the metadata and rollback tests share it and run in
    order (the rollback test reverts the state the metadata test observed).
    """

    @pytest.fixture(scope="class")
    async def update(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
    ) -> _AttributeKindUpdate:
        await load_schema(db=db, schema=SchemaRoot(**CAR_SCHEMA_TEXT), branch_name=default_branch_scope_class.name)

        car = await Node.init(db=db, schema="TestCar", branch=default_branch_scope_class)
        await car.new(db=db, name="Accord", description="A nice car")
        await car.save(db=db)

        return await _run_kind_update_migration(db=db, branch=default_branch_scope_class, node_uuid=car.id)

    async def test_migration_metadata(self, db: InfrahubDatabase, update: _AttributeKindUpdate) -> None:
        """The kind update bumps updated_at/by on the Node and Attribute and snapshots the prior values."""
        await _assert_migration_metadata(db=db, update=update)

    async def test_migration_rollback(self, db: InfrahubDatabase, update: _AttributeKindUpdate) -> None:
        """A range rollback undoes the migration: the branch edges and vertex metadata are restored, idempotently."""

        async def _run_rollback() -> None:
            await GraphRollbacker(db=db).rollback(
                target_branch=update.branch,
                at=update.migration_time,
                scope=RollbackScope.SINCE_TIMESTAMP,
            )

        await _run_rollback()
        await verify_graph(db=db)

        # The branch edges are restored exactly to their pre-migration state.
        assert await branch_edge_fingerprint(db=db, branch_name=update.branch.name) == update.pre_migration_fingerprint
        assert await branch_metadata_fingerprint(db=db, branch_name=update.branch.name) == update.pre_migration_metadata

        # The vertex metadata is restored to its pre-migration values and the snapshot is cleared.
        node_after, attr_after = await _get_car_and_description_metadata(db=db, node_uuid=update.node_id)
        assert node_after.updated_at == update.node_before.updated_at
        assert node_after.updated_by == update.node_before.updated_by
        assert node_after.previous_updated_at is None
        assert node_after.previous_updated_by is None
        assert attr_after.updated_at == update.attr_before.updated_at
        assert attr_after.updated_by == update.attr_before.updated_by
        assert attr_after.previous_updated_at is None
        assert attr_after.previous_updated_by is None

        # Running the rollback again is a no-op: nothing remains in the window to revert.
        await _run_rollback()
        await verify_graph(db=db)
        assert await branch_edge_fingerprint(db=db, branch_name=update.branch.name) == update.pre_migration_fingerprint
        assert await branch_metadata_fingerprint(db=db, branch_name=update.branch.name) == update.pre_migration_metadata
        node_again, attr_again = await _get_car_and_description_metadata(db=db, node_uuid=update.node_id)
        assert node_again == node_after
        assert attr_again == attr_after


async def test_migration_metadata_non_default_branch(db: InfrahubDatabase, default_branch: Branch) -> None:
    """On a user branch the kind update is reflected through edges but records no vertex-metadata snapshot."""
    await load_schema(db=db, schema=SchemaRoot(**CAR_SCHEMA_TEXT))

    car = await Node.init(db=db, schema="TestCar")
    await car.new(db=db, name="Accord", description="A nice car")
    await car.save(db=db)

    branch = await create_branch(branch_name="branch-attr-kind-update", db=db)
    update = await _run_kind_update_migration(db=db, branch=branch, node_uuid=car.id)
    await _assert_migration_metadata(db=db, update=update)
