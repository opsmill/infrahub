from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import GeneratorInstanceStatus, InfrahubKind, MetadataOptions, SchemaPathType
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from tests.db_snapshot import DbSnapshotter

from .conftest import get_diff_coordinator, get_diff_merger

if TYPE_CHECKING:
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
    before_merge = await NodeManager.get_one(
        db=db,
        branch=default_branch,
        id=target_instance.id,
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
        raise_on_error=True,
    )

    coordinator = await get_diff_coordinator(db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    merger = await get_diff_merger(db=db, branch=branch)
    snapshotter = DbSnapshotter(db=db)
    before_snapshot = await snapshotter.snapshot()
    before_edges = {edge.db_id: edge.properties for edge in before_snapshot.edge_map.values()}
    historical_at = Timestamp()
    merge_at = Timestamp()
    await merger.merge_graph(at=merge_at)

    assert await NodeManager.get_one(db=db, branch=default_branch, id=target.id) is None
    assert await NodeManager.get_one(db=db, branch=default_branch, id=target_instance.id) is None
    assert await NodeManager.get_one(db=db, branch=default_branch, id=other_instance.id) is not None
    assert await NodeManager.get_one(db=db, branch=default_branch, id=late_instance.id) is None
    assert await NodeManager.get_one(db=db, branch=sibling, id=sibling_instance.id) is not None
    at_merge = await NodeManager.get_one(db=db, branch=default_branch, at=merge_at, id=target_instance.id)
    assert at_merge is None
    historical = await NodeManager.get_one(
        db=db, branch=default_branch, at=historical_at, id=target_instance.id, raise_on_error=True
    )
    assert historical.get_attribute("name").value == "deleted-target-instance"
    assert (await historical.get_relationship("object").get_peer(db=db)).id == target.id
    inherited = await NodeManager.get_one(db=db, branch=sibling, id=target_instance.id, raise_on_error=True)
    assert (await inherited.get_relationship("object").get_peer(db=db)).id == target.id
    surviving_group = await NodeManager.get_one(db=db, branch=default_branch, id=query_group.id, raise_on_error=True)
    assert await surviving_group.get_relationship("subscribers").get_peers(db=db) == {}

    after_snapshot = await snapshotter.snapshot()
    after_edges = {edge.db_id: edge.properties for edge in after_snapshot.edge_map.values()}
    assert before_edges.keys() <= after_edges.keys()
    closed_edges = [
        props for edge_id, props in after_edges.items() if edge_id in before_edges and props != before_edges[edge_id]
    ]
    created_edges = [props for edge_id, props in after_edges.items() if edge_id not in before_edges]
    assert closed_edges
    assert created_edges
    for props in closed_edges:
        assert props["branch"] == default_branch.name
        assert props["status"] == "active"
        assert props["to"] == merge_at.to_string()
        assert props["from"] <= props["to"]
    for props in created_edges:
        assert props["branch"] == default_branch.name
        assert props["branch_level"] == default_branch.hierarchy_level
        assert props["status"] == "deleted"
        assert props["from"] == merge_at.to_string()
        assert props.get("to") is None
    await verify_graph(db=db)

    await merger.rollback(merge_started_at=merge_at)
    assert await NodeManager.get_one(db=db, branch=default_branch, id=target.id) is not None
    restored = await NodeManager.get_one(
        db=db,
        branch=default_branch,
        id=target_instance.id,
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
        raise_on_error=True,
    )
    assert (await restored.get_relationship("object").get_peer(db=db)).id == target.id
    assert restored._get_updated_at() == before_merge._get_updated_at()
    assert restored._get_updated_by() == before_merge._get_updated_by()
    restored_snapshot = await snapshotter.snapshot()
    assert {edge.db_id: edge.properties for edge in restored_snapshot.edge_map.values()} == before_edges
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
    merger = await get_diff_merger(db=db, branch=branch)
    await merger.merge_graph(at=Timestamp())

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
    merger = await get_diff_merger(db=db, branch=branch)
    await merger.merge_graph(at=Timestamp())

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
    merger = await get_diff_merger(db=db, branch=branch)
    await merger.merge_graph(at=Timestamp())

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
    merger = await get_diff_merger(db=db, branch=branch)
    await merger.merge_graph(at=Timestamp())

    assert await NodeManager.get_one(db=db, branch=default_branch, id=generator_definition.id) is None
    for instance in generator_instances:
        assert await NodeManager.get_one(db=db, branch=default_branch, id=instance.id) is None
    for target in (car_person_data_generic["c1"], car_person_data_generic["c2"]):
        assert await NodeManager.get_one(db=db, branch=default_branch, id=target.id) is not None
    await verify_graph(db=db)
