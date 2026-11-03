from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch.tasks import merge_branch
from infrahub.core.constants import GeneratorInstanceStatus, InfrahubKind, SchemaPathType
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.merge.generator_instance_cleaner import GeneratorInstanceCleaner
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from infrahub.workers.dependencies import build_cache, build_database, build_event_service
from tests.adapters.cache import MemoryCache
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.workflow import WorkflowRecorder
from tests.db_snapshot import DbSnapshotter
from tests.helpers.dependency_override import override_dependency
from tests.helpers.workflow_override import override_workflow

from .conftest import get_diff_coordinator, get_diff_merger

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def generator_definition(db: InfrahubDatabase, car_person_data_generic: dict[str, Node]) -> Node:
    group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await group.new(db=db, name="generator-targets")
    await group.save(db=db)
    definition = await Node.init(db=db, schema=InfrahubKind.GENERATORDEFINITION)
    await definition.new(
        db=db,
        name="car-generator",
        query=car_person_data_generic["q1"],
        repository=car_person_data_generic["r1"],
        targets=group,
        file_path="generators/car.py",
        class_name="CarGenerator",
        parameters={"value": {"name": "name__value"}},
    )
    await definition.save(db=db)
    return definition


async def _create_instance(db: InfrahubDatabase, branch: Branch, definition: Node, target: Node, name: str) -> Node:
    instance = await Node.init(db=db, branch=branch, schema=InfrahubKind.GENERATORINSTANCE)
    await instance.new(
        db=db, name=name, status=GeneratorInstanceStatus.READY.value, object=target, definition=definition
    )
    await instance.save(db=db)
    return instance


async def _merge(db: InfrahubDatabase, default_branch: Branch, branch: Branch, at: Timestamp) -> None:
    merger = await get_diff_merger(db=db, branch=branch)
    await merger.merge_graph(at=at)
    cleaner = GeneratorInstanceCleaner(
        db=db, source_branch=branch, destination_branch=default_branch, diff_repository=merger.diff_repository
    )
    instance_ids = await cleaner.find_orphaned_instances(merge_at=at)
    await cleaner.delete(instance_ids=instance_ids, user_id="merge-user")


@pytest.fixture
async def generator_instances(
    db: InfrahubDatabase, default_branch: Branch, generator_definition: Node, car_person_data_generic: dict[str, Node]
) -> tuple[Node, Node]:
    return (
        await _create_instance(
            db=db,
            branch=default_branch,
            definition=generator_definition,
            target=car_person_data_generic["c1"],
            name="deleted-target-instance",
        ),
        await _create_instance(
            db=db,
            branch=default_branch,
            definition=generator_definition,
            target=car_person_data_generic["c2"],
            name="retained-target-instance",
        ),
    )


async def test_merging_target_deletion_removes_destination_generator_instances(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_data_generic: dict[str, Node],
    generator_definition: Node,
    generator_instances: tuple[Node, Node],
) -> None:
    target = car_person_data_generic["c1"]
    target_instance, other_instance = generator_instances
    branch = await create_branch(db=db, branch_name="delete-generator-target")
    sibling = await create_branch(db=db, branch_name="retains-generator-target")
    sibling_instance = await _create_instance(
        db=db, branch=sibling, definition=generator_definition, target=target, name="sibling-instance"
    )
    late_instance = await _create_instance(
        db=db, branch=default_branch, definition=generator_definition, target=target, name="late-instance"
    )
    query_group = await Node.init(db=db, branch=default_branch, schema=InfrahubKind.GRAPHQLQUERYGROUP)
    await query_group.new(
        db=db,
        name="late-query-group",
        query=car_person_data_generic["q1"],
        subscribers=[target_instance, late_instance],
    )
    await query_group.save(db=db)
    target_on_branch = await NodeManager.get_one(db=db, branch=branch, id=target.id, raise_on_error=True)
    await NodeManager.delete(db=db, branch=branch, nodes=[target_on_branch])
    assert await NodeManager.get_one(db=db, branch=branch, id=target_instance.id) is None

    coordinator = await get_diff_coordinator(db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    historical_at = Timestamp()
    merge_at = Timestamp()
    await _merge(db=db, default_branch=default_branch, branch=branch, at=merge_at)

    assert await NodeManager.get_one(db=db, branch=default_branch, id=target.id) is None
    assert await NodeManager.get_one(db=db, branch=default_branch, id=target_instance.id) is None
    assert await NodeManager.get_one(db=db, branch=default_branch, id=other_instance.id) is not None
    assert await NodeManager.get_one(db=db, branch=default_branch, id=late_instance.id) is None
    assert await NodeManager.get_one(db=db, branch=sibling, id=sibling_instance.id) is not None
    # The delete lands after the merge timestamp, so a rollback of the merge never reverts it.
    assert await NodeManager.get_one(db=db, branch=default_branch, at=merge_at, id=target_instance.id) is not None
    historical = await NodeManager.get_one(
        db=db, branch=default_branch, at=historical_at, id=target_instance.id, raise_on_error=True
    )
    assert historical.get_attribute("name").value == "deleted-target-instance"
    assert (await historical.get_relationship("object").get_peer(db=db)).id == target.id
    inherited = await NodeManager.get_one(db=db, branch=sibling, id=target_instance.id, raise_on_error=True)
    assert (await inherited.get_relationship("object").get_peer(db=db)).id == target.id
    surviving_group = await NodeManager.get_one(db=db, branch=default_branch, id=query_group.id, raise_on_error=True)
    assert await surviving_group.get_relationship("subscribers").get_peers(db=db) == {}
    await verify_graph(db=db)


async def test_merge_rollback_restores_generator_instances_and_their_peers(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_data_generic: dict[str, Node],
    generator_definition: Node,
    generator_instances: tuple[Node, Node],
) -> None:
    target = car_person_data_generic["c1"]
    query_group = await Node.init(db=db, branch=default_branch, schema=InfrahubKind.GRAPHQLQUERYGROUP)
    await query_group.new(
        db=db, name="instance-query-group", query=car_person_data_generic["q1"], subscribers=[generator_instances[0]]
    )
    await query_group.save(db=db)
    branch = await create_branch(db=db, branch_name="rollback-generator-target")
    target_on_branch = await NodeManager.get_one(db=db, branch=branch, id=target.id, raise_on_error=True)
    await NodeManager.delete(db=db, branch=branch, nodes=[target_on_branch])
    coordinator = await get_diff_coordinator(db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    merger = await get_diff_merger(db=db, branch=branch)
    snapshotter = DbSnapshotter(db=db)
    before_snapshot = await snapshotter.snapshot()

    merge_at = Timestamp()
    await merger.merge_graph(at=merge_at)
    cleaner = GeneratorInstanceCleaner(
        db=db, source_branch=branch, destination_branch=default_branch, diff_repository=merger.diff_repository
    )
    assert await cleaner.find_orphaned_instances(merge_at=merge_at) == {generator_instances[0].id}
    await merger.rollback(merge_started_at=merge_at)

    restored_snapshot = await snapshotter.snapshot()
    assert {edge.db_id: edge.properties for edge in restored_snapshot.edge_map.values()} == {
        edge.db_id: edge.properties for edge in before_snapshot.edge_map.values()
    }
    assert {node.db_id: node.properties for node in restored_snapshot.node_map.values()} == {
        node.db_id: node.properties for node in before_snapshot.node_map.values()
    }
    await verify_graph(db=db)


async def test_target_deletion_resolved_to_base_preserves_generator_instances(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    car_person_data_generic: dict[str, Node],
    generator_instances: tuple[Node, Node],
) -> None:
    target = car_person_data_generic["c1"]
    branch = await create_branch(db=db, branch_name="keep-generator-target")
    target.get_attribute("name").value = "updated-on-main"
    await target.save(db=db)
    target_on_branch = await NodeManager.get_one(db=db, branch=branch, id=target.id, raise_on_error=True)
    await NodeManager.delete(db=db, branch=branch, nodes=[target_on_branch])

    coordinator = await get_diff_coordinator(db=db, branch=branch)
    diff = await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    conflicts = diff.get_all_conflicts()
    assert conflicts
    for conflict in conflicts.values():
        await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=ConflictSelection.BASE_BRANCH)
    await _merge(db=db, default_branch=default_branch, branch=branch, at=Timestamp())

    retained_target = await NodeManager.get_one(db=db, branch=default_branch, id=target.id, raise_on_error=True)
    assert retained_target.get_attribute("name").value == "updated-on-main"
    for instance in generator_instances:
        assert await NodeManager.get_one(db=db, branch=default_branch, id=instance.id) is not None
    await verify_graph(db=db)


async def test_retargeted_generator_instance_survives_previous_target_deletion(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_data_generic: dict[str, Node],
    generator_instances: tuple[Node, Node],
) -> None:
    target = car_person_data_generic["c1"]
    other_target = car_person_data_generic["c2"]
    instance = await NodeManager.get_one(
        db=db, branch=default_branch, id=generator_instances[0].id, raise_on_error=True
    )
    branch = await create_branch(db=db, branch_name="delete-previous-generator-target")
    await instance.get_relationship("object").update(db=db, data=other_target)
    await instance.save(db=db)
    target_on_branch = await NodeManager.get_one(db=db, branch=branch, id=target.id, raise_on_error=True)
    await NodeManager.delete(db=db, branch=branch, nodes=[target_on_branch])
    assert await NodeManager.get_one(db=db, branch=default_branch, id=instance.id) is not None
    coordinator = await get_diff_coordinator(db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    await _merge(db=db, default_branch=default_branch, branch=branch, at=Timestamp())

    assert await NodeManager.get_one(db=db, branch=default_branch, id=target.id) is None
    retained = await NodeManager.get_one(db=db, branch=default_branch, id=instance.id, raise_on_error=True)
    assert (await retained.get_relationship("object").get_peer(db=db)).id == other_target.id
    await verify_graph(db=db)


async def test_merging_deletion_of_migrated_target_removes_its_generator_instances(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    car_person_data_generic: dict[str, Node],
    generator_instances: tuple[Node, Node],
) -> None:
    target = car_person_data_generic["c1"]
    branch = await create_branch(db=db, branch_name="delete-migrated-generator-target")
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    previous_schema = schema_branch.get_node(name=target.get_kind())
    renamed_schema = deepcopy(previous_schema)
    renamed_schema.name = "RenamedElectricCar"
    schema_branch.set(name=renamed_schema.kind, schema=renamed_schema)
    schema_branch.process()
    await registry.schema.update_schema_branch(db=db, branch=default_branch, schema=schema_branch, update_db=True)
    migration = NodeKindUpdateMigration(
        previous_node_schema=previous_schema,
        new_node_schema=renamed_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=renamed_schema.kind, field_name="name"),
    )
    result = await migration.execute(
        migration_input=MigrationInput(db=db, at=Timestamp(), user_id="migration-user"), branch=default_branch
    )
    assert not result.errors
    migrated_target = await NodeManager.get_one(db=db, branch=default_branch, id=target.id, raise_on_error=True)
    assert migrated_target.get_kind() == "TestRenamedElectricCar"
    assert migrated_target.db_id != target.db_id

    target_on_branch = await NodeManager.get_one(db=db, branch=branch, id=target.id, raise_on_error=True)
    await NodeManager.delete(db=db, branch=branch, nodes=[target_on_branch])
    coordinator = await get_diff_coordinator(db=db, branch=branch)
    diff = await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    for conflict in diff.get_all_conflicts().values():
        await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=ConflictSelection.DIFF_BRANCH)
    await _merge(db=db, default_branch=default_branch, branch=branch, at=Timestamp())

    assert await NodeManager.get_one(db=db, branch=default_branch, id=target.id) is None
    assert await NodeManager.get_one(db=db, branch=default_branch, id=generator_instances[0].id) is None
    assert await NodeManager.get_one(db=db, branch=default_branch, id=generator_instances[1].id) is not None
    await verify_graph(db=db)


async def test_merging_definition_deletion_removes_destination_generator_instances(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_data_generic: dict[str, Node],
    generator_definition: Node,
    generator_instances: tuple[Node, Node],
) -> None:
    branch = await create_branch(db=db, branch_name="delete-generator-definition")
    definition_on_branch = await NodeManager.get_one(
        db=db, branch=branch, id=generator_definition.id, raise_on_error=True
    )
    await NodeManager.delete(db=db, branch=branch, nodes=[definition_on_branch])
    coordinator = await get_diff_coordinator(db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    await _merge(db=db, default_branch=default_branch, branch=branch, at=Timestamp())

    assert await NodeManager.get_one(db=db, branch=default_branch, id=generator_definition.id) is None
    for instance in generator_instances:
        assert await NodeManager.get_one(db=db, branch=default_branch, id=instance.id) is None
    for target in (car_person_data_generic["c1"], car_person_data_generic["c2"]):
        assert await NodeManager.get_one(db=db, branch=default_branch, id=target.id) is not None
    await verify_graph(db=db)


async def test_merging_target_and_definition_deletion_removes_each_instance_once(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_data_generic: dict[str, Node],
    generator_definition: Node,
    generator_instances: tuple[Node, Node],
) -> None:
    branch = await create_branch(db=db, branch_name="delete-generator-target-and-definition")
    target_on_branch = await NodeManager.get_one(
        db=db, branch=branch, id=car_person_data_generic["c1"].id, raise_on_error=True
    )
    definition_on_branch = await NodeManager.get_one(
        db=db, branch=branch, id=generator_definition.id, raise_on_error=True
    )
    await NodeManager.delete(db=db, branch=branch, nodes=[target_on_branch, definition_on_branch])
    coordinator = await get_diff_coordinator(db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    await _merge(db=db, default_branch=default_branch, branch=branch, at=Timestamp())

    for instance in generator_instances:
        assert await NodeManager.get_one(db=db, branch=default_branch, id=instance.id) is None
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $uuid})-[edge:IS_PART_OF {branch: $branch, status: "deleted"}]->(:Root)
        RETURN count(edge) AS deleted_edges
        """,
        params={"uuid": generator_instances[0].id, "branch": default_branch.name},
    )
    assert results[0]["deleted_edges"] == 1
    await verify_graph(db=db)


async def test_branch_merge_deletes_generator_instances_of_a_deleted_target(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_data_generic: dict[str, Node],
    generator_instances: tuple[Node, Node],
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    target = car_person_data_generic["c1"]
    branch = await create_branch(db=db, branch_name="merge-flow-generator-target")
    target_on_branch = await NodeManager.get_one(db=db, branch=branch, id=target.id, raise_on_error=True)
    await NodeManager.delete(db=db, branch=branch, nodes=[target_on_branch])
    event_recorder = MemoryInfrahubEvent()
    cache = MemoryCache()
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )

    with (
        override_dependency(build_database, lambda singleton=True: db, dependency_provider=dependency_provider),  # noqa: ARG005
        override_dependency(build_event_service, lambda: event_recorder, dependency_provider=dependency_provider),
        override_workflow(WorkflowRecorder(), dependency_provider=dependency_provider),
        override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider),
    ):
        await merge_branch(branch=branch.name, context=context)

    assert await NodeManager.get_one(db=db, branch=default_branch, id=target.id) is None
    assert await NodeManager.get_one(db=db, branch=default_branch, id=generator_instances[0].id) is None
    assert await NodeManager.get_one(db=db, branch=default_branch, id=generator_instances[1].id) is not None
    await verify_graph(db=db)
