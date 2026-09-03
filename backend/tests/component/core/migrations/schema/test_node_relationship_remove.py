"""Migration-level tests for the relationship-remove schema migration.

These component tests focus on:
 - the branch-aware edge semantics (in-place close on the operating branch vs. deleted shadow edges
   on a child branch)
 - idempotency
 - how the removal surfaces in a diff

``owner``/``cars`` are an inverse pair sharing one identifier and the same ``Relationship`` vertices, so
the data is only closed once both sides are removed from the schema. The helper below registers a
post-removal schema with every side of the identifier removed, matching what the update pipeline does
before migrations run.
"""

from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, SchemaPathType
from infrahub.core.diff.calculator import DiffCalculator
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.schema.node_relationship_remove import NodeRelationshipRemoveMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.query.rollback import RollbackScope
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_graph
from tests.helpers.vertex_metadata import (
    VertexMetadata,
    branch_edge_fingerprint,
    branch_metadata_fingerprint,
    get_node_vertex_metadata,
)


async def _prepare_removal(branch: Branch, node_kind: str, relationship_name: str) -> NodeRelationshipRemoveMigration:
    """Register a post-removal schema (both sides of the identifier removed) and return the migration."""
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous_node = schema_branch.get(name=node_kind)
    identifier = previous_node.get_relationship(relationship_name).get_identifier()

    candidate = schema_branch.duplicate()
    for sharing_schema in candidate.get_schemas_by_rel_identifier(identifier=identifier):
        node = candidate.get(name=sharing_schema.kind)
        node.relationships = [rel for rel in node.relationships if rel.identifier != identifier]
        candidate.set(name=sharing_schema.kind, schema=node)
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)

    return NodeRelationshipRemoveMigration(
        previous_node_schema=previous_node,
        new_node_schema=candidate.get(name=node_kind),
        schema_path=SchemaPath(
            path_type=SchemaPathType.RELATIONSHIP, schema_kind=node_kind, field_name=relationship_name
        ),
    )


async def _count_active_is_related(db: InfrahubDatabase, identifier: str, branch: Branch) -> int:
    query = """
    MATCH (n:Node)-[r:IS_RELATED]-(rel:Relationship {name: $identifier})
    WHERE r.status = "active" AND r.to IS NULL AND r.branch = $branch
    RETURN count(r) AS nbr
    """
    results = await db.execute_query(query=query, params={"identifier": identifier, "branch": branch.name})
    return results[0]["nbr"]


async def _get_relationship_vertices_metadata(
    db: InfrahubDatabase, identifier: str, branch_name: str
) -> list[VertexMetadata]:
    """Return the vertex metadata of every Relationship vertex of ``identifier`` reachable on ``branch_name``."""
    results = await db.execute_query(
        query=(
            "MATCH (rel:Relationship {name: $identifier}) "
            "WHERE exists((rel)-[:IS_RELATED {branch: $branch}]-()) "
            "RETURN rel.updated_at AS updated_at, rel.updated_by AS updated_by, "
            "rel.previous_updated_at AS previous_updated_at, rel.previous_updated_by AS previous_updated_by"
        ),
        params={"identifier": identifier, "branch": branch_name},
    )
    return [
        VertexMetadata(
            updated_at=row["updated_at"],
            updated_by=row["updated_by"],
            previous_updated_at=row["previous_updated_at"],
            previous_updated_by=row["previous_updated_by"],
        )
        for row in results
    ]


async def test_default_branch_closes_in_place(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node
) -> None:
    """On the operating branch, edges created there are closed in place and the migration is idempotent."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    identifier = schema.get(name="TestCar").get_relationship(name="owner").get_identifier()

    # Two cars linked to the same person -> 2 Relationship vertices, each with 2 IS_RELATED edges
    assert await _count_active_is_related(db=db, identifier=identifier, branch=default_branch) == 4

    migration = await _prepare_removal(branch=default_branch, node_kind="TestCar", relationship_name="owner")
    result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not result.errors
    assert result.nbr_migrations_executed == 2

    # On the default branch the active edges are closed in place (no shadow edges created)
    assert await _count_active_is_related(db=db, identifier=identifier, branch=default_branch) == 0

    # Idempotent re-run
    result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert result.nbr_migrations_executed == 0
    assert await _count_active_is_related(db=db, identifier=identifier, branch=default_branch) == 0

    await verify_graph(db=db)


async def test_user_branch_shadows_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node
) -> None:
    """Removing on a user branch shadows the default branch edges with deleted edges on the child."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    identifier = schema.get(name="TestCar").get_relationship(name="owner").get_identifier()

    branch = await create_branch(branch_name="branch-rel-remove", db=db)

    migration = await _prepare_removal(branch=branch, node_kind="TestCar", relationship_name="owner")
    result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not result.errors
    assert result.nbr_migrations_executed == 2

    # The default branch edges are untouched, the relationship is closed on the user branch
    assert await _count_active_is_related(db=db, identifier=identifier, branch=default_branch) == 4
    assert await _count_active_is_related(db=db, identifier=identifier, branch=branch) == 0

    # Idempotent re-run on the branch
    result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert result.nbr_migrations_executed == 0

    await verify_graph(db=db)


async def test_diff_shows_removed_for_preexisting_data(
    db: InfrahubDatabase, default_branch: Branch, person_john_main: Node, car_accord_main: Node
) -> None:
    """Removing a relationship from pre-existing data surfaces as REMOVED in the branch diff.

    The data was created on main, so on a child branch the migration writes deleted shadow edges,
    which the diff classifies as REMOVED (unlike a same-branch create+remove, which nets to unchanged
    because it is a no-op once merged).
    """
    branch = await create_branch(db=db, branch_name="branch-diff-rel-remove")
    from_time = Timestamp(branch.created_at)

    migration = await _prepare_removal(branch=branch, node_kind="TestCar", relationship_name="owner")
    result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not result.errors

    calculated_diffs = await DiffCalculator(db=db).calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )
    nodes_by_id = {n.uuid: n for n in calculated_diffs.diff_branch_diff.nodes}
    car_node = nodes_by_id[car_accord_main.id]
    owner_rel = next(rel for rel in car_node.relationships if rel.name == "owner")
    element = owner_rel.relationships[0]
    assert element.peer_id == person_john_main.id
    assert element.action is DiffAction.REMOVED

    await verify_graph(db=db)


@dataclass
class _RelationshipRemoval:
    """State captured around a single ``owner`` relationship-removal migration on one branch."""

    branch: Branch
    node_id: str
    identifier: str
    migration_time: Timestamp
    user_id: str
    node_before: VertexMetadata
    pre_migration_fingerprint: list[tuple]
    pre_migration_metadata: list[tuple]


async def _run_relationship_removal(db: InfrahubDatabase, branch: Branch, node_uuid: str) -> _RelationshipRemoval:
    """Run the ``owner``-relationship removal migration on ``branch`` and capture the surrounding state.

    Captures the pre-migration node vertex metadata and branch edge fingerprint so callers can assert
    the snapshot (default/global branch) and a rollback's restore.
    """
    schema = registry.schema.get_schema_branch(name=branch.name)
    identifier = schema.get(name="TestCar").get_relationship(name="owner").get_identifier()

    node_before = await get_node_vertex_metadata(db=db, node_uuid=node_uuid)
    pre_migration_fingerprint = await branch_edge_fingerprint(db=db, branch_name=branch.name)
    pre_migration_metadata = await branch_metadata_fingerprint(db=db, branch_name=branch.name)

    user_id = "migration_user"
    migration_time = Timestamp()

    migration = await _prepare_removal(branch=branch, node_kind="TestCar", relationship_name="owner")
    execution_result = await migration.execute(
        migration_input=MigrationInput(db=db, at=migration_time, user_id=user_id), branch=branch
    )
    assert not execution_result.errors

    return _RelationshipRemoval(
        branch=branch,
        node_id=node_uuid,
        identifier=identifier,
        migration_time=migration_time,
        user_id=user_id,
        node_before=node_before,
        pre_migration_fingerprint=pre_migration_fingerprint,
        pre_migration_metadata=pre_migration_metadata,
    )


async def _assert_migration_metadata(db: InfrahubDatabase, removal: _RelationshipRemoval) -> None:
    """Assert the removal's metadata effect, which differs by branch.

    On every branch the relationship is closed on the operating branch (in place on default/global, via
    deleted shadow edges on a user branch). Vertex-level metadata is maintained only on the
    default/global branch, so only there does the removal bump ``updated_at``/``by`` on the Node and the
    Relationship vertices and snapshot the prior values into ``previous_*``; on a user branch the shared
    vertices are left untouched.
    """
    assert await _count_active_is_related(db=db, identifier=removal.identifier, branch=removal.branch) == 0

    node_after = await get_node_vertex_metadata(db=db, node_uuid=removal.node_id)
    rel_metadatas = await _get_relationship_vertices_metadata(
        db=db, identifier=removal.identifier, branch_name=removal.branch.name
    )
    assert rel_metadatas, "Expected the Relationship vertices to be reachable on the operating branch"
    if removal.branch.is_default or removal.branch.is_global:
        # The bump snapshots the pre-migration values so a merge-failure rollback can restore them.
        assert node_after.updated_at == removal.migration_time.to_string()
        assert node_after.updated_by == removal.user_id
        assert node_after.previous_updated_at == removal.node_before.updated_at
        assert node_after.previous_updated_by == removal.node_before.updated_by

        # Every Relationship vertex is bumped to the migration timestamp and snapshots its prior values.
        for rel_metadata in rel_metadatas:
            assert rel_metadata.updated_at == removal.migration_time.to_string()
            assert rel_metadata.updated_by == removal.user_id
            assert rel_metadata.previous_updated_at is not None
            assert rel_metadata.previous_updated_at != removal.migration_time.to_string()
            assert rel_metadata.previous_updated_by is not None
    else:
        # A user-branch migration leaves the shared Node and Relationship vertices untouched, recording no snapshot.
        assert node_after == removal.node_before
        assert node_after.previous_updated_at is None
        assert node_after.previous_updated_by is None
        for rel_metadata in rel_metadatas:
            assert rel_metadata.updated_at != removal.migration_time.to_string()
            assert rel_metadata.previous_updated_at is None
            assert rel_metadata.previous_updated_by is None


class TestNodeRelationshipRemoveMetadata:
    """On the default branch, removing a relationship snapshots vertex metadata and a rollback restores it.

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
    ) -> _RelationshipRemoval:
        person = await Node.init(db=db, schema="TestPerson", branch=default_branch_scope_class)
        await person.new(db=db, name="John", height=180)
        await person.save(db=db)
        car = await Node.init(db=db, schema="TestCar", branch=default_branch_scope_class)
        await car.new(db=db, name="accord", color="#123456", owner=person.id)
        await car.save(db=db)

        return await _run_relationship_removal(db=db, branch=default_branch_scope_class, node_uuid=car.id)

    async def test_migration_metadata(self, db: InfrahubDatabase, removal: _RelationshipRemoval) -> None:
        """The removal bumps updated_at/by on the Node and Relationship vertices and snapshots prior values."""
        await _assert_migration_metadata(db=db, removal=removal)

    async def test_migration_rollback(self, db: InfrahubDatabase, removal: _RelationshipRemoval) -> None:
        """A range rollback undoes the migration: the branch edges and node metadata are restored, idempotently."""

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
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node
) -> None:
    """On a user branch the removal shadows the default edges but records no vertex-metadata snapshot."""
    branch = await create_branch(branch_name="branch-rel-remove-meta", db=db)
    removal = await _run_relationship_removal(db=db, branch=branch, node_uuid=car_accord_main.id)
    await _assert_migration_metadata(db=db, removal=removal)
