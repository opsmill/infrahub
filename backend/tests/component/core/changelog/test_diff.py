from typing import Literal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from infrahub.core.branch import Branch
from infrahub.core.changelog.builder import build_diff_changelog_collector
from infrahub.core.changelog.models import RelationshipCardinalityManyChangelog, RelationshipCardinalityOneChangelog
from infrahub.core.constants import DiffAction, InfrahubKind, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from tests.component.core.diff.get_one_node import get_one_diff_node
from tests.helpers.diff_factories import (
    EnrichedNodeFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)


async def test_events_from_diff(
    db: InfrahubDatabase, default_branch: Branch, base_dataset_02: dict, register_core_models_schema: SchemaBranch
) -> None:
    branch1 = await Branch.get_by_name(name="branch1", db=db)
    at = Timestamp()
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch1)
    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch1)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch1)
    await diff_merger.merge_graph(at=at)
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch1)
    diff = await diff_repository.get_one(diff_branch_name=branch1.name)
    diff_events = build_diff_changelog_collector(diff=diff, db=db, branch=branch1)
    changelogs = await diff_events.collect_changelogs()
    assert len(changelogs) == 2


async def test_merge_diff_changelogs(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_simplified_proposed_change_schema: SchemaBranch,
    car_person_schema: None,
    first_account: Node,
    second_account: Node,
) -> None:
    third_account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await third_account.new(db=db, name="Third Account", account_type="Git", password="ThirdPassword123")
    await third_account.save(db=db)

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
        name={"value": "Volvo", "owner": first_account, "source": p2},
        nbr_seats=5,
        is_electric=False,
        owner={"id": p1.id, "_relation__source": p2.id, "_relation__owner": third_account.id},
    )
    await car1.save(db=db)

    branch5 = await create_branch(db=db, branch_name="branch5")

    p4 = await Node.init(db=db, schema="TestPerson", branch=branch5)
    await p4.new(db=db, name="George", height=180)
    await p4.save(db=db)

    car1_update = await NodeManager.get_one(id=car1.id, kind="TestCar", db=db, branch=branch5)
    car1_update.name.value = "Volvo 240"
    car1_update.name.source = p1
    car1_update.name.owner = second_account
    await car1_update.owner.update(
        data={"id": p2.id, "_relation__source": p3.id, "_relation__owner": second_account.id}, db=db
    )
    await car1_update.save(db=db)

    car2 = await Node.init(db=db, schema="TestCar", branch=branch5)
    await car2.new(
        db=db,
        name={"value": "Saab", "owner": first_account, "source": p2},
        nbr_seats=5,
        is_electric=False,
        owner={"id": p1.id, "_relation__source": p1.id, "_relation__owner": first_account.id},
    )
    await car2.save(db=db)

    at = Timestamp()

    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch5)
    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch5)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch5)
    await diff_merger.merge_graph(at=at)
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch5)
    diff = await diff_repository.get_one(diff_branch_name=branch5.name)
    diff_events = build_diff_changelog_collector(diff=diff, db=db, branch=branch5)
    events = await diff_events.collect_changelogs()
    assert len(events) == 5
    changelogs = [changelog[1] for changelog in events]
    p1_changelog = next(node for node in changelogs if node.node_id == p1.id)
    p2_changelog = next(node for node in changelogs if node.node_id == p2.id)
    p4_changelog = next(node for node in changelogs if node.node_id == p4.id)
    c1_changelog = next(node for node in changelogs if node.node_id == car1.id)
    c2_changelog = next(node for node in changelogs if node.node_id == car2.id)

    assert not p1_changelog.attributes
    assert "cars" in p1_changelog.relationships
    assert isinstance(p1_changelog.relationships["cars"], RelationshipCardinalityManyChangelog)
    assert len(p1_changelog.relationships["cars"].peers) == 2
    peer_car1 = next(peer for peer in p1_changelog.relationships["cars"].peers if peer.peer_id == car1.id)
    peer_car2 = next(peer for peer in p1_changelog.relationships["cars"].peers if peer.peer_id == car2.id)
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
    assert c1_changelog.attributes["name"].properties["owner"].value == second_account.id
    assert c1_changelog.attributes["name"].properties["owner"].value_previous == first_account.id
    assert c1_changelog.attributes["human_friendly_id"].value_update_status == DiffAction.UPDATED
    assert c1_changelog.attributes["human_friendly_id"].value == '["Volvo 240"]'
    assert c1_changelog.attributes["human_friendly_id"].value_previous == '["Volvo"]'
    assert len(c1_changelog.relationships.keys()) == 1
    assert isinstance(c1_changelog.relationships["owner"], RelationshipCardinalityOneChangelog)
    assert c1_changelog.relationships["owner"].peer_kind == "TestPerson"
    assert c1_changelog.relationships["owner"].peer_id == p2.id
    assert c1_changelog.relationships["owner"].peer_id_previous == p1.id
    assert c1_changelog.relationships["owner"].properties["owner"].value == second_account.id
    assert c1_changelog.relationships["owner"].properties["owner"].value_previous == third_account.id
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
    assert c2_changelog.relationships["owner"].properties["owner"].value == first_account.id
    assert c2_changelog.relationships["owner"].properties["owner"].value_previous is None
    assert c2_changelog.relationships["owner"].properties["source"].value == p1.id
    assert c2_changelog.relationships["owner"].properties["source"].value_previous is None


async def test_merge_changelog_reads_an_attribute_owner_that_an_earlier_release_stored_in_the_diff(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_simplified_proposed_change_schema: SchemaBranch,
    car_person_schema: None,
    first_account: Node,
    second_account: Node,
) -> None:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name={"value": "John", "owner": first_account}, height=180)
    await person.save(db=db)
    branch = await create_branch(db=db, branch_name="branch_old_diff")
    person_branch = await NodeManager.get_one(db=db, id=person.id, branch=branch)
    person_branch.name.owner = second_account
    await person_branch.save(db=db)
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    # An earlier release stored the owner ID alone, not a list of owner IDs.
    await db.execute_query(
        query="""
        MATCH (:DiffNode {uuid: $node_id})-[:DIFF_HAS_ATTRIBUTE]->(:DiffAttribute {name: "name"})
            -[:DIFF_HAS_PROPERTY]->(owner:DiffProperty {property_type: "HAS_OWNER"})
        SET owner.previous_value = $previous, owner.new_value = $new
        """,
        params={"node_id": person.id, "previous": first_account.id, "new": second_account.id},
    )
    person_branch = await NodeManager.get_one(db=db, id=person.id, branch=branch)
    person_branch.height.value = 181
    await person_branch.save(db=db)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    diff = await diff_repository.get_one(diff_branch_name=branch.name)
    owner_property = (
        get_one_diff_node(diff_root=diff, node_uuid=person.id)
        .get_attribute(name="name")
        .get_property(property_type=DatabaseEdgeType.HAS_OWNER)
    )
    assert owner_property.new_value == second_account.id

    at = Timestamp()
    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
    await diff_merger.merge_graph(at=at)
    changelogs = await build_diff_changelog_collector(
        diff=diff, db=db, branch=default_branch, merge_at=at
    ).collect_changelogs()

    changelog = next(changelog for _, changelog in changelogs if changelog.node_id == person.id)
    owner_changes = {
        name: (prop.value_previous, prop.value) for name, prop in changelog.attributes["name"].properties.items()
    }
    assert owner_changes == {"owner": (first_account.id, second_account.id)}


class TestConflict:
    @pytest.fixture(autouse=True)
    async def _setup_proposed_change_schema(self, register_simplified_proposed_change_schema: SchemaBranch) -> None:
        return

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
        ("conflict_selection", "expected_value"),
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
    ) -> None:
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
        await diff_merger.merge_graph(at=at)
        diff = await diff_repository.get_one(diff_branch_name=branch2.name)
        diff_events = build_diff_changelog_collector(diff=diff, db=db, branch=branch2)
        events = await diff_events.collect_changelogs()

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
    ) -> None:
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
        await diff_merger.merge_graph(at=at)
        diff = await diff_repository.get_one(diff_branch_name=branch2.name)
        diff_events = build_diff_changelog_collector(diff=diff, db=db, branch=branch2)
        events = await diff_events.collect_changelogs()
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


async def test_changelog_of_a_relationship_missing_from_the_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: None
) -> None:
    """A relationship a schema migration removed keeps its changelog, with an unknown peer kind."""
    peer_id = str(uuid4())
    relationship = EnrichedRelationshipGroupFactory.build(
        name="removed_relationship",
        cardinality=RelationshipCardinality.MANY,
        action=DiffAction.UPDATED,
        relationships={
            EnrichedRelationshipElementFactory.build(peer_id=peer_id, action=DiffAction.ADDED, properties=set())
        },
        nodes=set(),
    )
    node = EnrichedNodeFactory.build(
        kind="TestPerson", action=DiffAction.UPDATED, attributes=set(), relationships={relationship}
    )

    changelogs = await build_diff_changelog_collector(
        diff=EnrichedRootFactory.build(nodes={node}), db=db, branch=default_branch
    ).collect_changelogs()

    assert [(action, changelog.node_id) for action, changelog in changelogs] == [(DiffAction.UPDATED, node.uuid)]
    relationship_changelog = changelogs[0][1].relationships["removed_relationship"]
    assert isinstance(relationship_changelog, RelationshipCardinalityManyChangelog)
    assert [(peer.peer_id, peer.peer_kind) for peer in relationship_changelog.peers] == [(peer_id, "n/a")]
