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

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, SchemaPathType
from infrahub.core.diff.calculator import DiffCalculator
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.schema.node_relationship_remove import NodeRelationshipRemoveMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.db_validation import verify_graph


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


async def test_short_circuit_when_relationship_absent_from_schemas(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node
) -> None:
    """The migration runs no query when the removed relationship is absent from both node schemas.

    This is the rebase case: the branch schema is already aligned with the destination, so the removed
    relationship's identifier cannot be recovered and the migration must short-circuit rather than fail.
    """
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    identifier = schema.get(name="TestCar").get_relationship(name="owner").get_identifier()

    # A TestCar schema with 'owner' already removed, used as both the previous and new node schema
    aligned_car = schema.duplicate().get(name="TestCar")
    aligned_car.relationships = [rel for rel in aligned_car.relationships if rel.name != "owner"]

    migration = NodeRelationshipRemoveMigration(
        previous_node_schema=aligned_car,
        new_node_schema=aligned_car,
        schema_path=SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestCar", field_name="owner"),
    )
    result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not result.errors
    assert result.nbr_migrations_executed == 0

    # No query ran, so the existing relationship data is left untouched
    assert await _count_active_is_related(db=db, identifier=identifier, branch=default_branch) == 4

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
