from typing import Literal
from unittest.mock import AsyncMock

import pytest

from infrahub.core.branch import Branch
from infrahub.core.changelog.diff import DiffChangelogCollector
from infrahub.core.changelog.models import RelationshipCardinalityManyChangelog, RelationshipCardinalityOneChangelog
from infrahub.core.constants import DiffAction
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry


async def test_events_from_diff(
    db: InfrahubDatabase, default_branch, base_dataset_02, register_core_models_schema
) -> None:
    branch1 = await Branch.get_by_name(name="branch1", db=db)
    at = Timestamp()
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch1)
    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch1)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch1)
    diff = await diff_merger.merge_graph(at=at)
    diff_events = DiffChangelogCollector(diff=diff, db=db, branch=branch1)
    changelogs = diff_events.collect_changelogs()
    assert len(changelogs) == 3


async def test_merge_diff_changelogs(db: InfrahubDatabase, default_branch, car_person_schema: None) -> None:
    p1 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    p2 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await p2.new(db=db, name={"value": "Jimmy", "source": p1}, height=180)
    await p2.save(db=db)

    p3 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await p3.new(db=db, name={"value": "Jimmy in main", "source": p1}, height=180)
    await p3.save(db=db)

    car1 = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car1.new(
        db=db,
        name={"value": "Volvo", "owner": p1, "source": p2},
        nbr_seats=5,
        is_electric=False,
        owner={"id": p1.id, "_relation__source": p2.id, "_relation__owner": p3.id},
    )
    await car1.save(db=db)

    branch5 = await create_branch(db=db, branch_name="branch5")

    p4 = await Node.init(db=db, schema="TestPerson", branch=branch5)
    await p4.new(db=db, name="George", height=180)
    await p4.save(db=db)

    car1_update = await NodeManager.get_one(id=car1.id, kind="TestCar", db=db, branch=branch5)
    car1_update.name.value = "Volvo 240"
    car1_update.name.source = p1
    car1_update.name.owner = p2
    await car1_update.owner.update(data={"id": p2.id, "_relation__source": p3.id, "_relation__owner": p2.id}, db=db)
    await car1_update.save(db=db)

    car2 = await Node.init(db=db, schema="TestCar", branch=branch5)
    await car2.new(
        db=db,
        name={"value": "Saab", "owner": p1, "source": p2},
        nbr_seats=5,
        is_electric=False,
        owner={"id": p1.id, "_relation__source": p1.id, "_relation__owner": p1.id},
    )
    await car2.save(db=db)

    at = Timestamp()

    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch5)
    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch5)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch5)
    diff = await diff_merger.merge_graph(at=at)
    diff_events = DiffChangelogCollector(diff=diff, db=db, branch=branch5)
    events = diff_events.collect_changelogs()
    assert len(events) == 5
    changelogs = [changelog[1] for changelog in events]
    p1_changelog = [node for node in changelogs if node.node_id == p1.id][0]
    p2_changelog = [node for node in changelogs if node.node_id == p2.id][0]
    p4_changelog = [node for node in changelogs if node.node_id == p4.id][0]
    c1_changelog = [node for node in changelogs if node.node_id == car1.id][0]
    c2_changelog = [node for node in changelogs if node.node_id == car2.id][0]

    assert not p1_changelog.attributes
    assert "cars" in p1_changelog.relationships
    assert isinstance(p1_changelog.relationships["cars"], RelationshipCardinalityManyChangelog)
    assert len(p1_changelog.relationships["cars"].peers) == 2
    peer_car1 = [peer for peer in p1_changelog.relationships["cars"].peers if peer.peer_id == car1.id][0]
    peer_car2 = [peer for peer in p1_changelog.relationships["cars"].peers if peer.peer_id == car2.id][0]
    assert peer_car1.peer_status == DiffAction.REMOVED
    assert peer_car2.peer_status == DiffAction.ADDED

    assert not p2_changelog.attributes
    assert "cars" in p2_changelog.relationships
    assert isinstance(p2_changelog.relationships["cars"], RelationshipCardinalityManyChangelog)
    assert len(p2_changelog.relationships["cars"].peers) == 1
    assert p2_changelog.relationships["cars"].peers[0].peer_id == car1.id

    assert len(p4_changelog.attributes.keys()) == 4
    assert p4_changelog.attributes["name"].value_update_status == DiffAction.ADDED
    assert p4_changelog.attributes["height"].value_update_status == DiffAction.ADDED
    assert p4_changelog.attributes["display_label"].value_update_status == DiffAction.ADDED
    assert not p4_changelog.relationships

    assert len(c1_changelog.attributes.keys()) == 3
    assert c1_changelog.attributes["name"].value_update_status == DiffAction.UPDATED
    assert c1_changelog.attributes["name"].value == "Volvo 240"
    assert c1_changelog.attributes["name"].value_previous == "Volvo"
    assert c1_changelog.attributes["display_label"].value_update_status == DiffAction.UPDATED
    assert c1_changelog.attributes["display_label"].value == "Volvo 240 #444444"
    assert c1_changelog.attributes["display_label"].value_previous == "Volvo #444444"
    assert c1_changelog.attributes["name"].properties["owner"].value == p2.id
    assert c1_changelog.attributes["name"].properties["owner"].value_previous == p1.id
    assert c1_changelog.attributes["human_friendly_id"].value_update_status == DiffAction.UPDATED
    assert c1_changelog.attributes["human_friendly_id"].value == '["Volvo 240"]'
    assert c1_changelog.attributes["human_friendly_id"].value_previous == '["Volvo"]'
    assert len(c1_changelog.relationships.keys()) == 1
    assert isinstance(c1_changelog.relationships["owner"], RelationshipCardinalityOneChangelog)
    assert c1_changelog.relationships["owner"].peer_kind == "TestPerson"
    assert c1_changelog.relationships["owner"].peer_id == p2.id
    assert c1_changelog.relationships["owner"].peer_id_previous == p1.id
    assert c1_changelog.relationships["owner"].properties["owner"].value == p2.id
    assert c1_changelog.relationships["owner"].properties["owner"].value_previous == p3.id
    assert c1_changelog.relationships["owner"].properties["source"].value == p3.id
    assert c1_changelog.relationships["owner"].properties["source"].value_previous == p2.id

    assert sorted(c2_changelog.attributes.keys()) == [
        "color",
        "display_label",
        "human_friendly_id",
        "is_electric",
        "name",
        "nbr_seats",
        "transmission",
    ]
    assert len(c2_changelog.relationships.keys()) == 1
    assert isinstance(c2_changelog.relationships["owner"], RelationshipCardinalityOneChangelog)
    assert c2_changelog.relationships["owner"].properties["owner"].value == p1.id
    assert c2_changelog.relationships["owner"].properties["owner"].value_previous is None
    assert c2_changelog.relationships["owner"].properties["source"].value == p1.id
    assert c2_changelog.relationships["owner"].properties["source"].value_previous is None


class TestConflict:
    async def _get_diff_coordinator(self, db: InfrahubDatabase, branch: Branch) -> DiffCoordinator:
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
        return diff_coordinator

    async def _get_diff_merger(self, db: InfrahubDatabase, branch: Branch) -> DiffMerger:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffMerger, db=db, branch=branch)

    @pytest.fixture
    async def diff_repository(self, db: InfrahubDatabase, default_branch: Branch) -> DiffRepository:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffRepository, db=db, branch=default_branch)

    @pytest.mark.parametrize(
        "conflict_selection,expected_value",
        [(ConflictSelection.BASE_BRANCH, "John-main"), (ConflictSelection.DIFF_BRANCH, "John-branch")],
    )
    async def test_diff_and_merge_with_attribute_value_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main: Node,
        person_jane_main: Node,
        person_alfred_main: Node,
        car_accord_main: Node,
        conflict_selection: ConflictSelection,
        expected_value: Literal["John-main", "John-branch"],
    ):
        branch2 = await create_branch(db=db, branch_name="branch2")
        john_main = await NodeManager.get_one(db=db, id=person_john_main.id)
        john_main.name.value = "John-main"
        await john_main.save(db=db)
        john_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_john_main.id)
        john_branch.name.value = "John-branch"
        await john_branch.save(db=db)

        at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch2
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 3
        for conflict in conflicts_map.values():
            await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=conflict_selection)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        diff = await diff_merger.merge_graph(at=at)
        diff_events = DiffChangelogCollector(diff=diff, db=db, branch=branch2)
        events = diff_events.collect_changelogs()

        match conflict_selection:
            case ConflictSelection.BASE_BRANCH:
                # When we want to keep the conflict in the base branch we don't expect to see any updates after the merge
                assert len(events) == 0
            case ConflictSelection.DIFF_BRANCH:
                # Expect to see changes on the diff branch when we keep changes from that branch
                assert len(events) == 1
                event = events[0]
                action, node_changelog = event
                assert action == DiffAction.UPDATED
                assert node_changelog.attributes["name"].value == "John-branch"
                assert node_changelog.attributes["name"].value_previous == "John"
                assert node_changelog.attributes["human_friendly_id"].value == '["John-branch"]'
                assert node_changelog.attributes["human_friendly_id"].value_previous == '["John"]'
                assert node_changelog.attributes["display_label"].value == "John-branch"
                assert node_changelog.attributes["display_label"].value_previous == "John"

    @pytest.mark.parametrize(
        "conflict_selection",
        [ConflictSelection.BASE_BRANCH, ConflictSelection.DIFF_BRANCH],
    )
    async def test_diff_and_merge_with_attribute_property_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        diff_repository: DiffRepository,
        person_john_main: Node,
        person_jane_main: Node,
        person_alfred_main: Node,
        car_accord_main: Node,
        conflict_selection: ConflictSelection,
    ):
        branch2 = await create_branch(db=db, branch_name="branch2")
        john_main = await NodeManager.get_one(db=db, id=person_john_main.id)
        john_main.name.source = person_alfred_main
        await john_main.save(db=db)
        john_branch = await NodeManager.get_one(db=db, branch=branch2, id=person_john_main.id)
        john_branch.name.source = person_jane_main
        await john_branch.save(db=db)

        at = Timestamp()
        diff_coordinator = await self._get_diff_coordinator(db=db, branch=branch2)
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch2
        )
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        conflicts_map = enriched_diff.get_all_conflicts()
        assert len(conflicts_map) == 1
        conflict = next(iter(conflicts_map.values()))
        await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=conflict_selection)
        diff_merger = await self._get_diff_merger(db=db, branch=branch2)
        diff = await diff_merger.merge_graph(at=at)
        diff_events = DiffChangelogCollector(diff=diff, db=db, branch=branch2)
        events = diff_events.collect_changelogs()
        match conflict_selection:
            case ConflictSelection.BASE_BRANCH:
                # When we want to keep the conflict in the base branch we don't expect to see any updates after the merge
                assert len(events) == 0
            case ConflictSelection.DIFF_BRANCH:
                # Expect to see changes on the diff branch when we keep changes from that branch
                assert len(events) == 1
                event = events[0]
                action, node_changelog = event
                assert action == DiffAction.UPDATED
                assert node_changelog.attributes["name"].properties["source"].value == person_jane_main.id
                assert node_changelog.attributes["name"].properties["source"].value_previous is None
