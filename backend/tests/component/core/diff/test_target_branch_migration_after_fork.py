"""Merging a delete from a user branch when the same UUID was kind-migrated on
the target branch *after* the user branch was forked must propagate the delete
(and its metadata) to the post-migration Node vertex on the target branch.
"""

from unittest.mock import AsyncMock

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry


async def _get_diff_coordinator(db: InfrahubDatabase, branch: Branch) -> DiffCoordinator:
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
    return diff_coordinator


async def _get_diff_merger(db: InfrahubDatabase, branch: Branch) -> DiffMerger:
    component_registry = get_component_registry()
    return await component_registry.get_component(DiffMerger, db=db, branch=branch)


async def _migrate_testcar_to_test2newcar_on_default(
    db: InfrahubDatabase,
    default_branch: Branch,
) -> Timestamp:
    main_schema = registry.schema.get_schema_branch(name=default_branch.name)
    original_car_schema = main_schema.get(name="TestCar", duplicate=True)
    new_car_schema = main_schema.get(name="TestCar", duplicate=True)
    new_car_schema.name = "NewCar"
    new_car_schema.namespace = "Test2"
    assert new_car_schema.kind == "Test2NewCar"
    main_schema.set(name="Test2NewCar", schema=new_car_schema)
    person_schema = main_schema.get(name="TestPerson", duplicate=True)
    person_schema.get_relationship("cars").peer = "Test2NewCar"
    person_schema.get_relationship("cars_driven").peer = "Test2NewCar"
    main_schema.set(name="TestPerson", schema=person_schema)
    main_schema.delete(name="TestCar")
    main_schema.process()
    await registry.schema.update_schema_branch(
        db=db,
        branch=default_branch,
        schema=main_schema,
        limit=["TestCar", "Test2NewCar", "TestPerson"],
        update_db=True,
    )
    migration = NodeKindUpdateMigration(
        previous_node_schema=original_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"),
    )
    migration_at = Timestamp()
    result = await migration.execute(
        migration_input=MigrationInput(db=db, at=migration_at, user_id="migration-user"),
        branch=default_branch,
    )
    assert not result.errors
    return migration_at


async def test_target_branch_migration_after_fork_delete_propagates_to_post_migration_vertex(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    person_jane_main: Node,
    car_camry_main: Node,
) -> None:
    """Post-migration ``Test2NewCar`` vertex must be fully deleted by the merge:
    its active ``IS_PART_OF`` and child edges closed at ``merge_at``, and its
    node-level ``updated_at`` / ``updated_by`` refreshed to reflect the delete.
    """
    branch_user = "branch-deleted-node-user"

    # Fork the diff branch while the schema is still TestCar, then migrate
    # TestCar -> Test2NewCar on default, then delete on the branch.
    branch = await create_branch(db=db, branch_name="tgt-migration-after-fork")
    migration_at = await _migrate_testcar_to_test2newcar_on_default(db=db, default_branch=default_branch)

    branch_car = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    assert branch_car is not None
    await branch_car.delete(db=db, user_id=branch_user)

    coordinator = await _get_diff_coordinator(db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    merger = await _get_diff_merger(db=db, branch=branch)
    merge_at = Timestamp()
    await merger.merge_graph(at=merge_at)

    # Dump every IS_PART_OF on the default branch for the deleted UUID so the
    # failure is self-describing.
    ipo_rows = await db.execute_query(
        query="""
        MATCH (n:Node {uuid: $uuid})-[ipo:IS_PART_OF {branch: $target_branch}]->(:Root)
        RETURN labels(n) AS labels,
               n.updated_at AS node_updated_at,
               n.updated_by AS node_updated_by,
               ipo.status AS status,
               ipo.from AS ipo_from,
               ipo.to AS ipo_to,
               ipo.to_user_id AS ipo_to_user_id
        ORDER BY ipo_from, status
        """,
        params={"uuid": car_camry_main.id, "target_branch": default_branch.name},
    )
    diag = (
        f"\nmigration_at = {migration_at.to_string()}"
        f"\nmerge_at     = {merge_at.to_string()}"
        f"\nIS_PART_OF rows on {default_branch.name!r} for {car_camry_main.id}:\n"
        + "\n".join("  " + repr(r) for r in ipo_rows)
    )

    new_vertex_ipos = [r for r in ipo_rows if "Test2NewCar" in r["labels"]]
    old_vertex_ipos = [r for r in ipo_rows if "Test2NewCar" not in r["labels"] and "TestCar" in r["labels"]]
    assert old_vertex_ipos, f"expected a pre-migration TestCar IS_PART_OF{diag}"
    assert new_vertex_ipos, f"expected a post-migration Test2NewCar IS_PART_OF{diag}"

    # The active IS_PART_OF on the post-migration vertex must be closed at
    # merge_at, attributed to the branch user.
    new_active_ipo = [r for r in new_vertex_ipos if r["status"] == "active"]
    assert len(new_active_ipo) == 1, f"expected exactly one active IS_PART_OF on the post-migration vertex{diag}"
    assert new_active_ipo[0]["ipo_to"] == merge_at.to_string(), (
        "post-migration Test2NewCar IS_PART_OF was not closed by the merge "
        f"(expected ipo.to == merge_at, got {new_active_ipo[0]['ipo_to']!r}){diag}"
    )
    assert new_active_ipo[0]["ipo_to_user_id"] == branch_user, (
        "post-migration Test2NewCar IS_PART_OF was not closed by the branch user "
        f"(expected ipo.to_user_id == {branch_user!r}, got {new_active_ipo[0]['ipo_to_user_id']!r}){diag}"
    )

    # Child edges (HAS_ATTRIBUTE/IS_RELATED) on the post-migration vertex must
    # also be closed.
    open_child_edges = await db.execute_query(
        query="""
        MATCH (n:Test2NewCar {uuid: $uuid})-[e:HAS_ATTRIBUTE|IS_RELATED]-(field:Attribute|Relationship)
        WHERE e.branch = $target_branch
        AND e.status = "active"
        AND e.to IS NULL
        RETURN type(e) AS edge_type, labels(field) AS field_labels, e.from AS e_from
        """,
        params={"uuid": car_camry_main.id, "target_branch": default_branch.name},
    )
    assert not open_child_edges, (
        "post-migration Test2NewCar vertex still has active target-branch HAS_ATTRIBUTE/IS_RELATED "
        f"edges after a delete-merge: {open_child_edges!r}{diag}"
    )

    # Node-level metadata on the post-migration vertex must reflect the merge,
    # not the prior migration.
    new_node_updated_at = new_active_ipo[0]["node_updated_at"]
    new_node_updated_by = new_active_ipo[0]["node_updated_by"]
    assert new_node_updated_at == merge_at.to_string(), (
        "post-migration Test2NewCar n.updated_at not refreshed by the merge "
        f"(expected {merge_at.to_string()}, got {new_node_updated_at!r}){diag}"
    )
    assert new_node_updated_by == branch_user, (
        "post-migration Test2NewCar n.updated_by not refreshed by the merge "
        f"(expected {branch_user!r}, got {new_node_updated_by!r}){diag}"
    )

    # Conversely, the pre-migration ``TestCar`` vertex must NOT have its
    # node-level metadata clobbered by the merge
    old_node_updated_at = old_vertex_ipos[0]["node_updated_at"]
    old_node_updated_by = old_vertex_ipos[0]["node_updated_by"]
    assert old_node_updated_at != merge_at.to_string(), (
        "pre-migration TestCar n.updated_at was clobbered to merge_at by the merge "
        f"(merge did not add or close any edges on this vertex){diag}"
    )
    assert old_node_updated_by != branch_user, (
        "pre-migration TestCar n.updated_by was clobbered to the branch user by the merge "
        f"(merge did not add or close any edges on this vertex){diag}"
    )
