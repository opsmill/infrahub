from infrahub.core.branch import Branch
from infrahub.core.changelog.diff import DiffChangelogCollector
from infrahub.core.changelog.models import RelationshipCardinalityManyChangelog, RelationshipCardinalityOneChangelog
from infrahub.core.constants import DiffAction
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.merger.merger import DiffMerger
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

    assert len(p4_changelog.attributes.keys()) == 2
    assert p4_changelog.attributes["name"].value_update_status == DiffAction.ADDED
    assert p4_changelog.attributes["height"].value_update_status == DiffAction.ADDED
    assert not p4_changelog.relationships

    assert len(c1_changelog.attributes.keys()) == 1
    assert c1_changelog.attributes["name"].value_update_status == DiffAction.UPDATED
    assert c1_changelog.attributes["name"].value == "Volvo 240"
    assert c1_changelog.attributes["name"].value_previous == "Volvo"
    assert c1_changelog.attributes["name"].properties["owner"].value == p2.id
    assert c1_changelog.attributes["name"].properties["owner"].value_previous == p1.id
    assert len(c1_changelog.relationships.keys()) == 1
    assert isinstance(c1_changelog.relationships["owner"], RelationshipCardinalityOneChangelog)
    assert c1_changelog.relationships["owner"].peer_kind == "TestPerson"
    assert c1_changelog.relationships["owner"].peer_id == p2.id
    assert c1_changelog.relationships["owner"].peer_id_previous == p1.id
    assert c1_changelog.relationships["owner"].properties["owner"].value == p2.id
    assert c1_changelog.relationships["owner"].properties["owner"].value_previous == p3.id
    assert c1_changelog.relationships["owner"].properties["source"].value == p3.id
    assert c1_changelog.relationships["owner"].properties["source"].value_previous == p2.id

    assert sorted(c2_changelog.attributes.keys()) == ["color", "is_electric", "name", "nbr_seats", "transmission"]
    assert len(c2_changelog.relationships.keys()) == 1
    assert isinstance(c2_changelog.relationships["owner"], RelationshipCardinalityOneChangelog)
    assert c2_changelog.relationships["owner"].properties["owner"].value == p1.id
    assert c2_changelog.relationships["owner"].properties["owner"].value_previous is None
    assert c2_changelog.relationships["owner"].properties["source"].value == p1.id
    assert c2_changelog.relationships["owner"].properties["source"].value_previous is None
