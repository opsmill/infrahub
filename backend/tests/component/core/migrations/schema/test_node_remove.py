from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_remove import (
    NodeRemoveMigration,
    NodeRemoveMigrationQueryIn,
    NodeRemoveMigrationQueryOut,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
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
from tests.component.core.migrations.schema.test_node_kind_update import validate_node_relationships
from tests.db_snapshot import DbSnapshotter
from tests.helpers.db_validation import verify_graph
from tests.helpers.edge_timestamps import assert_edge_timestamps
from tests.helpers.schema import load_schema


@dataclass
class _FieldRow:
    """One torn-down Attribute/Relationship of a removed node: its closed edge plus its vertex metadata."""

    name: str
    uuid: str
    from_user_id: str | None
    from_time: str | None
    metadata: VertexMetadata


async def _get_car_field_metadata(db: InfrahubDatabase, node_uuid: str, branch_name: str) -> list[_FieldRow]:
    """Return the deleted Attribute/Relationship fields of a removed TestCar and their vertex metadata."""
    query = """
        MATCH (n:TestCar {uuid: $node_uuid})
        MATCH (n)-[r:HAS_ATTRIBUTE|IS_RELATED {branch: $branch, status: "deleted"}]-(field)
        RETURN r.from_user_id AS from_user_id, r.from AS from_time,
            field.updated_at AS updated_at, field.updated_by AS updated_by,
            field.previous_updated_at AS previous_updated_at, field.previous_updated_by AS previous_updated_by,
            field.name AS name, field.uuid AS uuid
    """
    results = await db.execute_query(query=query, params={"node_uuid": node_uuid, "branch": branch_name})
    return [
        _FieldRow(
            name=row["name"],
            uuid=row["uuid"],
            from_user_id=row["from_user_id"],
            from_time=row["from_time"],
            metadata=VertexMetadata(
                updated_at=row["updated_at"],
                updated_by=row["updated_by"],
                previous_updated_at=row["previous_updated_at"],
                previous_updated_by=row["previous_updated_by"],
            ),
        )
        for row in results
    ]


async def test_query_out_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    candidate_schema.delete(name="TestCar")

    assert await count_nodes(db=db, label="TestCar") == 2

    count_rels = await count_relationships(db=db)

    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )
    query = await NodeRemoveMigrationQueryOut.init(db=db, branch=default_branch, migration=migration)

    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 2

    # we expect 25 new relationships per TestCar, 50 TOTAL:
    # - 9 deleted parent edges (7 attributes, 1 outbound relationship, 1 IS_PART_OF)
    # - 16 deleted sub-edges (HAS_VALUE + IS_PROTECTED per attribute = 14, plus
    #   far-side IS_RELATED + IS_PROTECTED per outbound relationship = 2)
    assert await count_relationships(db=db) == count_rels + 50
    assert await count_nodes(db=db, label="TestCar") == 2

    # Re-execute the query once to ensure that it won't change anything
    query = await NodeRemoveMigrationQueryOut.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0
    assert await count_relationships(db=db) == count_rels + 50
    assert await count_nodes(db=db, label="TestCar") == 2


async def test_query_in_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    """This test is a bit silly for now because there is nothing to migrate but it least we validate that the generated query is valid."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    candidate_schema.delete(name="TestCar")

    assert await count_nodes(db=db, label="TestCar") == 2

    count_rels = await count_relationships(db=db)

    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )
    query = await NodeRemoveMigrationQueryIn.init(db=db, branch=default_branch, migration=migration)

    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0

    # we expect 0 new relationships because there is no inbound relationships defined currently
    assert await count_relationships(db=db) == count_rels + 0
    assert await count_nodes(db=db, label="TestCar") == 2

    # Re-execute the query once to ensure that it won't change anything
    query = await NodeRemoveMigrationQueryIn.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0
    assert await count_relationships(db=db) == count_rels + 0
    assert await count_nodes(db=db, label="TestCar") == 2


async def test_migration_aware(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    candidate_schema.delete(name="TestCar")

    # 1. Snapshot before migration
    snapshotter = DbSnapshotter(db)
    before_snapshot = await snapshotter.snapshot()

    # 2. Create explicit timestamp
    at = Timestamp()
    at_str = at.to_string()

    # 3. Count nodes and relationships before migration
    assert await count_nodes(db=db, label="TestCar") == 2
    count_rels = await count_relationships(db=db)

    # 4. Execute migration
    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2

    # 5. Validate nodes and relationships after migration
    assert await count_relationships(db=db) == count_rels + 50
    assert await count_nodes(db=db, label="TestCar") == 2

    # 6. Validate edge timestamps
    after_snapshot = await snapshotter.snapshot()
    assert_edge_timestamps(before_snapshot, after_snapshot, at_str)

    # 7. Validate node relationships
    await validate_node_relationships(node=car_accord_main, db=db, branch=default_branch)
    await validate_node_relationships(node=car_camry_main, db=db, branch=default_branch)

    # 8. Validate graph integrity
    await verify_graph(db=db)


async def test_migration_aware_inbound_relationship(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
) -> None:
    """Remove TestPerson, exercising the IN query path for IS_RELATED.

    TestPerson.cars is defined with `direction: inbound`, so IS_RELATED edges from
    TestPerson's perspective are stored as `Relationship -> TestPerson`. Removing
    TestPerson must close the Relationship vertex's other sub-edges (IS_PROTECTED,
    far-side IS_RELATED to TestCar) — verify_graph would otherwise flag orphaned
    active sub-edges.
    """
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    candidate_schema.delete(name="TestPerson")

    # car_accord_main creates person_john_main, car_camry_main creates person_jane_main
    assert await count_nodes(db=db, label="TestPerson") == 2
    assert await count_nodes(db=db, label="TestCar") == 2

    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name="TestPerson"),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestPerson"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors

    # Cars themselves remain; only TestPerson nodes' edges are torn down.
    assert await NodeManager.count(db=db, schema="TestCar", branch=default_branch) == 2
    assert await NodeManager.count(db=db, schema="TestPerson", branch=default_branch) == 0

    await verify_graph(db=db)


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
    candidate_schema.delete(name="TestCar")

    assert await count_nodes(db=db, label="TestCar") == 1

    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 1
    assert await count_nodes(db=db, label="TestCar") == 1

    await validate_node_relationships(node=person_john, db=db, branch=registry.get_global_branch())
    await validate_node_relationships(node=car, db=db, branch=registry.get_global_branch())

    await verify_graph(db=db)


@dataclass
class _NodeRemoval:
    """State captured around a single TestCar node-removal migration on one branch."""

    branch: Branch
    node_id: str
    migration_time: Timestamp
    user_id: str
    node_before: VertexMetadata
    pre_migration_fingerprint: list[tuple]
    pre_migration_metadata: list[tuple]


async def _run_node_remove_migration(db: InfrahubDatabase, branch: Branch, node_uuid: str) -> _NodeRemoval:
    """Run the TestCar node-removal migration on ``branch`` and capture the surrounding state.

    Captures the pre-migration node vertex metadata and branch edge fingerprint so callers can assert
    the snapshot (default/global branch) and a rollback's restore.
    """
    node_before = await get_node_vertex_metadata(db=db, node_uuid=node_uuid)
    pre_migration_fingerprint = await branch_edge_fingerprint(db=db, branch_name=branch.name)
    pre_migration_metadata = await branch_metadata_fingerprint(db=db, branch_name=branch.name)

    user_id = "migration_user"
    migration_time = Timestamp()

    schema = registry.schema.get_schema_branch(name=branch.name)
    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )
    execution_result = await migration.execute(
        migration_input=MigrationInput(db=db, at=migration_time, user_id=user_id), branch=branch
    )
    assert not execution_result.errors

    return _NodeRemoval(
        branch=branch,
        node_id=node_uuid,
        migration_time=migration_time,
        user_id=user_id,
        node_before=node_before,
        pre_migration_fingerprint=pre_migration_fingerprint,
        pre_migration_metadata=pre_migration_metadata,
    )


async def _assert_migration_metadata(db: InfrahubDatabase, removal: _NodeRemoval) -> None:
    """Assert the removal's metadata effect, which differs by branch.

    On every branch the change is reflected through the closed edges (the deleted IS_PART_OF edge to
    Root and the closed HAS_ATTRIBUTE/IS_RELATED edges), which carry the migration user/timestamp.
    Vertex-level metadata is maintained only on the default/global branch, so only there does the
    removal bump ``updated_at``/``by`` on the node and its fields and snapshot the prior values into
    ``previous_*``; on a user branch the shared vertices are left untouched.
    """
    node_after = await get_node_vertex_metadata(db=db, node_uuid=removal.node_id)
    if removal.branch.is_default or removal.branch.is_global:
        # The bump snapshots the pre-migration values so a merge-failure rollback can restore them. The
        # node vertex is pre-existing and survives a rollback, so it too needs a snapshot.
        assert node_after.updated_at == removal.migration_time.to_string()
        assert node_after.updated_by == removal.user_id
        assert node_after.previous_updated_at == removal.node_before.updated_at
        assert node_after.previous_updated_by == removal.node_before.updated_by
    else:
        # A user-branch migration leaves the shared node vertex untouched and records no snapshot.
        assert node_after == removal.node_before
        assert node_after.previous_updated_at is None

    # The removal closes the IS_PART_OF edge to Root with the migration's user/timestamp.
    edge_results = await db.execute_query(
        query="""
        MATCH (n:TestCar {uuid: $node_uuid})-[r:IS_PART_OF {branch: $branch, status: "deleted"}]->(:Root)
        RETURN r.from_user_id AS from_user_id, r.from AS from_time
        """,
        params={"node_uuid": removal.node_id, "branch": removal.branch.name},
    )
    assert len(edge_results) == 1, "Expected exactly one deleted IS_PART_OF edge"
    assert edge_results[0]["from_user_id"] == removal.user_id
    assert edge_results[0]["from_time"] == removal.migration_time.to_string()

    # The node's Attributes/Relationships are torn down; each closed edge carries the migration user/time.
    fields = await _get_car_field_metadata(db=db, node_uuid=removal.node_id, branch_name=removal.branch.name)
    assert fields, "Expected at least one deleted HAS_ATTRIBUTE/IS_RELATED edge"
    for field in fields:
        assert field.from_user_id == removal.user_id, f"Wrong from_user_id on edge to {field.name} ({field.uuid})"
        assert field.from_time == removal.migration_time.to_string(), (
            f"Wrong from_time on edge to {field.name} ({field.uuid})"
        )
        if removal.branch.is_default or removal.branch.is_global:
            assert field.metadata.updated_at == removal.migration_time.to_string(), (
                f"Wrong updated_at on {field.name} ({field.uuid})"
            )
            assert field.metadata.updated_by == removal.user_id, f"Wrong updated_by on {field.name} ({field.uuid})"
            assert field.metadata.previous_updated_at is not None, (
                f"Missing previous_updated_at on {field.name} ({field.uuid})"
            )
            assert field.metadata.previous_updated_at != removal.migration_time.to_string(), (
                f"previous_updated_at was not snapshotted before the bump on {field.name} ({field.uuid})"
            )
            assert field.metadata.previous_updated_by is not None, (
                f"Missing previous_updated_by on {field.name} ({field.uuid})"
            )
        else:
            # A user-branch migration records no snapshot on the shared field vertices.
            assert field.metadata.previous_updated_at is None, f"Unexpected snapshot on {field.name} ({field.uuid})"


class TestNodeRemoveMetadata:
    """On the default branch, removing a node snapshots vertex metadata and a rollback restores it.

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
    ) -> _NodeRemoval:
        person = await Node.init(db=db, schema="TestPerson", branch=default_branch_scope_class)
        await person.new(db=db, name="John", height=180)
        await person.save(db=db)
        car = await Node.init(db=db, schema="TestCar", branch=default_branch_scope_class)
        await car.new(db=db, name="accord", color="#123456", owner=person.id)
        await car.save(db=db)

        return await _run_node_remove_migration(db=db, branch=default_branch_scope_class, node_uuid=car.id)

    async def test_migration_metadata(self, db: InfrahubDatabase, removal: _NodeRemoval) -> None:
        """The removal bumps updated_at/by on the node and its fields and snapshots the prior values."""
        await _assert_migration_metadata(db=db, removal=removal)

    async def test_migration_rollback(self, db: InfrahubDatabase, removal: _NodeRemoval) -> None:
        """The rollback undoes the migration: the branch edges and vertex metadata are restored, idempotently."""

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

        # The node vertex metadata is restored to its pre-migration values and the snapshot is cleared.
        node_after = await get_node_vertex_metadata(db=db, node_uuid=removal.node_id)
        assert node_after.updated_at == removal.node_before.updated_at
        assert node_after.updated_by == removal.node_before.updated_by
        assert node_after.previous_updated_at is None
        assert node_after.previous_updated_by is None

        # Running the rollback again is a no-op: nothing remains in the window to revert.
        await _run_rollback()
        await verify_graph(db=db)
        assert (
            await branch_edge_fingerprint(db=db, branch_name=removal.branch.name) == removal.pre_migration_fingerprint
        )
        assert (
            await branch_metadata_fingerprint(db=db, branch_name=removal.branch.name) == removal.pre_migration_metadata
        )
        node_again = await get_node_vertex_metadata(db=db, node_uuid=removal.node_id)
        assert node_again == node_after


async def test_migration_metadata_non_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node
) -> None:
    """On a user branch the removal is reflected through edges but records no vertex-metadata snapshot."""
    branch = await create_branch(branch_name="branch-node-remove-meta", db=db)
    removal = await _run_node_remove_migration(db=db, branch=branch, node_uuid=car_accord_main.id)
    await _assert_migration_metadata(db=db, removal=removal)
