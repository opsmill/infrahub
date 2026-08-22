from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SYSTEM_USER_ID, MetadataOptions, RelationshipHierarchyDirection, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration, NodeKindUpdateMigrationQuery01
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.query.node import NodeGetHierarchyQuery
from infrahub.core.query.rollback import RollbackScope
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase
from tests.component.core.migrations.schema.metadata_helpers import (
    VertexMetadata,
    branch_edge_fingerprint,
    branch_metadata_fingerprint,
    get_node_vertex_metadata,
)
from tests.constants import TestKind
from tests.db_snapshot import DbSnapshotter
from tests.helpers.db_validation import (
    validate_node_relationships,
    verify_graph,
    verify_no_duplicate_paths,
)
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


async def _get_original_car_metadata(db: InfrahubDatabase, node_uuid: str, branch_name: str) -> VertexMetadata:
    """Return the metadata of the ORIGINAL ``:TestCar`` vertex after the migration.

    The kind change creates a new ``:Test2NewCar`` vertex sharing the uuid, so the original is
    disambiguated by its now-deleted IS_PART_OF edge on ``branch_name``. The original vertex is the one
    that survives a rollback and holds the meaningful ``previous_*`` snapshot.
    """
    query = """
        MATCH (n:TestCar {uuid: $node_uuid})-[:IS_PART_OF {branch: $branch, status: "deleted"}]->(:Root)
        RETURN n.updated_at AS updated_at, n.updated_by AS updated_by,
            n.previous_updated_at AS previous_updated_at, n.previous_updated_by AS previous_updated_by
    """
    results = await db.execute_query(query=query, params={"node_uuid": node_uuid, "branch": branch_name})
    row = results[0]
    return VertexMetadata(
        updated_at=row["updated_at"],
        updated_by=row["updated_by"],
        previous_updated_at=row["previous_updated_at"],
        previous_updated_by=row["previous_updated_by"],
    )


@dataclass
class _NodeKindUpdate:
    """State captured around a single ``TestCar`` -> ``Test2NewCar`` kind-update migration on one branch."""

    branch: Branch
    node_id: str
    migration_time: Timestamp
    user_id: str
    car_created_at: Timestamp
    node_before: VertexMetadata
    pre_migration_fingerprint: list[tuple]
    pre_migration_metadata: list[tuple]


async def _run_node_kind_update_migration(db: InfrahubDatabase, branch: Branch, node_uuid: str) -> _NodeKindUpdate:
    """Rename ``TestCar`` to ``Test2NewCar`` on ``branch`` and capture the surrounding state.

    Captures the pre-migration node created_at, vertex metadata and branch edge fingerprint so callers
    can assert the snapshot (default/global branch) and a rollback's restore.
    """
    car_before = await NodeManager.get_one(
        db=db,
        branch=branch,
        id=node_uuid,
        include_metadata=MetadataQueryOptions(node_level=MetadataOptions.USER_TIMESTAMPS),
    )
    assert car_before is not None
    car_created_at = car_before._get_created_at()
    assert car_created_at is not None

    node_before = await get_node_vertex_metadata(db=db, node_uuid=node_uuid)
    pre_migration_fingerprint = await branch_edge_fingerprint(db=db, branch_name=branch.name)
    pre_migration_metadata = await branch_metadata_fingerprint(db=db, branch_name=branch.name)

    user_id = "migration_user"
    migration_time = Timestamp()

    schema = registry.schema.get_schema_branch(name=branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    candidate_schema.delete(name="TestCar")
    car_schema.name = "NewCar"
    car_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewCar", schema=car_schema)

    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"),
    )
    execution_result = await migration.execute(
        migration_input=MigrationInput(db=db, at=migration_time, user_id=user_id), branch=branch
    )
    assert not execution_result.errors

    registry.schema.set_schema_branch(name=branch.name, schema=candidate_schema)

    return _NodeKindUpdate(
        branch=branch,
        node_id=node_uuid,
        migration_time=migration_time,
        user_id=user_id,
        car_created_at=car_created_at,
        node_before=node_before,
        pre_migration_fingerprint=pre_migration_fingerprint,
        pre_migration_metadata=pre_migration_metadata,
    )


async def _assert_migration_metadata(db: InfrahubDatabase, update: _NodeKindUpdate) -> None:
    """Assert the kind-update's metadata effect, which differs by branch.

    On every branch the change is reflected through the ORM view of the migrated node and through the
    edges (a new active edge set on the ``:Test2NewCar`` vertex and the closed edge on the original
    ``:TestCar`` vertex, both stamped with the migration's user). Vertex-level metadata is maintained
    only on the default/global branch, so only there does the migration bump ``updated_at``/``by`` on the
    surviving original vertex and snapshot the prior values into ``previous_*``; on a user branch the
    shared vertex is left untouched.
    """
    updated_car = await NodeManager.get_one(
        db=db,
        branch=update.branch,
        id=update.node_id,
        include_metadata=MetadataQueryOptions(
            node_level=MetadataOptions.USER_TIMESTAMPS,
            attribute_level=MetadataOptions.USER_TIMESTAMPS,
            relationship_level=MetadataOptions.USER_TIMESTAMPS,
        ),
        prefetch_relationships=True,
    )
    assert updated_car._get_created_at() == update.car_created_at
    assert updated_car._get_created_by() == SYSTEM_USER_ID
    assert updated_car._get_updated_at() == update.migration_time
    assert updated_car._get_updated_by() == update.user_id
    for attr_name in updated_car.get_schema().attribute_names:
        attr = updated_car.get_attribute(name=attr_name)
        assert attr._get_created_at() == update.car_created_at
        assert attr._get_created_by() == SYSTEM_USER_ID
        assert attr._get_updated_at() == attr._get_created_at()
        assert attr._get_updated_by() == SYSTEM_USER_ID
    rel_manager = updated_car.get_relationship(name="owner")
    rels = await rel_manager.get_relationships(db=db)
    assert len(rels) == 1
    rel = rels[0]
    assert rel._get_created_at() == update.car_created_at
    assert rel._get_created_by() == SYSTEM_USER_ID
    assert rel._get_updated_at() == rel._get_created_at()
    assert rel._get_updated_by() == SYSTEM_USER_ID

    # The NEW active edges on the migrated node carry the migration's user/timestamp.
    new_edge_results = await db.execute_query(
        query="""
        MATCH (:Test2NewCar {uuid: $node_uuid})-[r {branch: $branch, status: "active", from: $migration_time}]-()
        RETURN DISTINCT r.from_user_id AS from_user_id
        """,
        params={
            "node_uuid": update.node_id,
            "branch": update.branch.name,
            "migration_time": update.migration_time.to_string(),
        },
    )
    assert len(new_edge_results) == 1, "Expected exactly one active edge on migrated node"
    assert new_edge_results[0]["from_user_id"] == update.user_id

    # The OLD deleted edges on the original node carry the same migration user/timestamp.
    old_edge_results = await db.execute_query(
        query="""
        MATCH (:TestCar {uuid: $node_uuid})-[r {branch: $branch, status: "deleted", from: $migration_time}]-()
        RETURN DISTINCT r.from_user_id AS from_user_id
        """,
        params={
            "node_uuid": update.node_id,
            "branch": update.branch.name,
            "migration_time": update.migration_time.to_string(),
        },
    )
    assert len(old_edge_results) == 1, "Expected exactly one deleted edge on old node"
    assert old_edge_results[0]["from_user_id"] == update.user_id

    original_after = await _get_original_car_metadata(db=db, node_uuid=update.node_id, branch_name=update.branch.name)
    if update.branch.is_default or update.branch.is_global:
        # The kind change replaces the node with a new vertex; the original (now deleted) vertex keeps the
        # pre-migration snapshot so a merge-failure rollback can restore it after deleting the new one.
        assert original_after.updated_at == update.migration_time.to_string()
        assert original_after.updated_by == update.user_id
        assert original_after.previous_updated_at == update.node_before.updated_at
        assert original_after.previous_updated_by == update.node_before.updated_by
    else:
        # A user-branch migration leaves the shared vertex untouched and records no snapshot.
        assert original_after.previous_updated_at is None
        assert original_after.previous_updated_by is None


class TestNodeKindUpdateMetadata:
    """On the default branch, updating a node's kind snapshots vertex metadata and a rollback restores it.

    A class-scoped fixture runs the migration once; the metadata and rollback tests share it and run in
    order (the rollback test reverts the state the metadata test observed).
    """

    @pytest.fixture(scope="class")
    async def update(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
        car_person_schema_scope_class: SchemaBranch,
    ) -> _NodeKindUpdate:
        person = await Node.init(db=db, schema="TestPerson", branch=default_branch_scope_class)
        await person.new(db=db, name="John", height=180)
        await person.save(db=db)
        car = await Node.init(db=db, schema="TestCar", branch=default_branch_scope_class)
        await car.new(db=db, name="accord", nbr_seats=5, is_electric=False, owner=person.id)
        await car.save(db=db)

        return await _run_node_kind_update_migration(db=db, branch=default_branch_scope_class, node_uuid=car.id)

    async def test_migration_metadata(self, db: InfrahubDatabase, update: _NodeKindUpdate) -> None:
        """The kind change bumps updated_at/by on the surviving original vertex and snapshots the prior values."""
        await _assert_migration_metadata(db=db, update=update)

    async def test_migration_rollback(self, db: InfrahubDatabase, update: _NodeKindUpdate) -> None:
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

        # The rollback deletes the new Test2NewCar vertex and reopens the original, restoring its metadata.
        node_after = await get_node_vertex_metadata(db=db, node_uuid=update.node_id)
        assert node_after.updated_at == update.node_before.updated_at
        assert node_after.updated_by == update.node_before.updated_by
        assert node_after.previous_updated_at is None
        assert node_after.previous_updated_by is None

        # Running the rollback again is a no-op: nothing remains in the window to revert.
        await _run_rollback()
        await verify_graph(db=db)
        assert await branch_edge_fingerprint(db=db, branch_name=update.branch.name) == update.pre_migration_fingerprint
        assert await branch_metadata_fingerprint(db=db, branch_name=update.branch.name) == update.pre_migration_metadata
        node_again = await get_node_vertex_metadata(db=db, node_uuid=update.node_id)
        assert node_again == node_after


async def test_migration_metadata_non_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node
) -> None:
    """On a user branch the kind change is reflected through edges but records no vertex-metadata snapshot."""
    branch = await create_branch(branch_name="branch-kind-update-meta", db=db)
    update = await _run_node_kind_update_migration(db=db, branch=branch, node_uuid=car_accord_main.id)
    await _assert_migration_metadata(db=db, update=update)
