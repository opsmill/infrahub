from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, InfrahubKind
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.calculator import DiffCalculator
from infrahub.core.diff.model.field_specifiers_map import NodeFieldSpecifierMap
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


async def test_relationship_one_peer_branch_and_main_update(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_jane_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    await car_main.owner.update(db=db, data={"id": person_jane_main.id})
    before_main_change = Timestamp()
    await car_main.save(db=db)
    after_main_change = Timestamp()
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await car_branch.owner.update(db=db, data={"id": person_alfred_main.id})
    before_branch_change = Timestamp()
    await car_branch.save(db=db)
    after_branch_change = Timestamp()

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    # check branch
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    nodes_by_id = {n.uuid: n for n in branch_root_path.nodes}
    assert set(nodes_by_id.keys()) == {car_accord_main.id, person_john_main.id, person_alfred_main.id}
    # check relationship on car node on branch
    car_node = nodes_by_id[car_main.get_id()]
    assert car_node.uuid == car_accord_main.id
    assert car_node.kind == "TestCar"
    assert car_node.action is DiffAction.UPDATED
    assert car_node.is_node_kind_migration is False
    assert len(car_node.attributes) == 0
    assert len(car_node.relationships) == 1
    relationship_diff = car_node.relationships[0]
    assert relationship_diff.name == "owner"
    assert relationship_diff.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in relationship_diff.relationships}
    assert set(elements_by_peer_id.keys()) == {person_john_main.id, person_alfred_main.id}
    removed_relationship = elements_by_peer_id[person_john_main.id]
    assert removed_relationship.peer_id == person_john_main.id
    assert removed_relationship.action is DiffAction.REMOVED
    properties_by_type = {p.property_type: p for p in removed_relationship.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    assert {(p.property_type, p.action, p.previous_value, p.new_value) for p in removed_relationship.properties} == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.REMOVED, person_john_main.id, None),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.REMOVED, False, None),
    }
    for prop_diff in removed_relationship.properties:
        assert before_branch_change < prop_diff.changed_at < after_branch_change
    added_relationship = elements_by_peer_id[person_alfred_main.id]
    assert added_relationship.peer_id == person_alfred_main.id
    assert added_relationship.action is DiffAction.ADDED
    properties_by_type = {p.property_type: p for p in added_relationship.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    assert {(p.property_type, p.action, p.previous_value, p.new_value) for p in added_relationship.properties} == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.ADDED, None, person_alfred_main.id),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.ADDED, None, False),
    }
    for prop_diff in added_relationship.properties:
        assert before_branch_change < prop_diff.changed_at < after_branch_change
    # check relationship on removed peer on branch
    john_node = nodes_by_id[person_john_main.get_id()]
    assert john_node.uuid == person_john_main.get_id()
    assert john_node.kind == "TestPerson"
    assert john_node.action is DiffAction.UPDATED
    assert john_node.is_node_kind_migration is False
    assert len(john_node.attributes) == 0
    assert len(john_node.relationships) == 1
    relationship_diff = john_node.relationships[0]
    assert relationship_diff.name == "cars"
    assert relationship_diff.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in relationship_diff.relationships}
    assert set(elements_by_peer_id.keys()) == {car_accord_main.get_id()}
    single_relationship = relationship_diff.relationships[0]
    assert single_relationship.peer_id == car_accord_main.id
    assert single_relationship.action is DiffAction.REMOVED
    properties_by_type = {p.property_type: p for p in single_relationship.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    assert {(p.property_type, p.action, p.previous_value, p.new_value) for p in single_relationship.properties} == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.REMOVED, car_accord_main.id, None),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.REMOVED, False, None),
    }
    for prop_diff in single_relationship.properties:
        assert before_branch_change < prop_diff.changed_at < after_branch_change
    # check relationship on added peer on branch
    alfred_node = nodes_by_id[person_alfred_main.get_id()]
    assert alfred_node.uuid == person_alfred_main.get_id()
    assert alfred_node.kind == "TestPerson"
    assert alfred_node.action is DiffAction.UPDATED
    assert alfred_node.is_node_kind_migration is False
    assert len(alfred_node.attributes) == 0
    assert len(alfred_node.relationships) == 1
    relationship_diff = alfred_node.relationships[0]
    assert relationship_diff.name == "cars"
    assert relationship_diff.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in relationship_diff.relationships}
    assert set(elements_by_peer_id.keys()) == {car_accord_main.get_id()}
    single_relationship = relationship_diff.relationships[0]
    assert single_relationship.peer_id == car_accord_main.id
    assert single_relationship.action is DiffAction.ADDED
    properties_by_type = {p.property_type: p for p in single_relationship.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    assert {(p.property_type, p.action, p.previous_value, p.new_value) for p in single_relationship.properties} == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.ADDED, None, car_accord_main.id),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.ADDED, None, False),
    }
    for prop_diff in single_relationship.properties:
        assert before_branch_change < prop_diff.changed_at < after_branch_change
    # check main
    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.branch == default_branch.name
    nodes_by_id = {n.uuid: n for n in base_root_path.nodes}
    assert set(nodes_by_id.keys()) == {car_accord_main.id, person_john_main.id}
    # check relationship on car node on main
    car_node = nodes_by_id[car_main.get_id()]
    assert car_node.uuid == car_accord_main.id
    assert car_node.kind == "TestCar"
    assert car_node.action is DiffAction.UPDATED
    assert car_node.is_node_kind_migration is False
    assert len(car_node.attributes) == 0
    assert len(car_node.relationships) == 1
    relationship_diff = car_node.relationships[0]
    assert relationship_diff.name == "owner"
    assert relationship_diff.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in relationship_diff.relationships}
    assert set(elements_by_peer_id.keys()) == {person_john_main.id, person_jane_main.id}
    removed_relationship = elements_by_peer_id[person_john_main.id]
    assert removed_relationship.peer_id == person_john_main.id
    assert removed_relationship.action is DiffAction.REMOVED
    properties_by_type = {p.property_type: p for p in removed_relationship.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    assert {(p.property_type, p.action, p.previous_value, p.new_value) for p in removed_relationship.properties} == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.REMOVED, person_john_main.id, None),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.REMOVED, False, None),
    }
    for prop_diff in removed_relationship.properties:
        assert before_main_change < prop_diff.changed_at < after_main_change
    added_relationship = elements_by_peer_id[person_jane_main.id]
    assert added_relationship.peer_id == person_jane_main.id
    assert added_relationship.action is DiffAction.ADDED
    properties_by_type = {p.property_type: p for p in added_relationship.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    assert {(p.property_type, p.action, p.previous_value, p.new_value) for p in added_relationship.properties} == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.ADDED, None, person_jane_main.id),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.ADDED, None, False),
    }
    for prop_diff in added_relationship.properties:
        assert before_main_change < prop_diff.changed_at < after_main_change

    # check relationship on removed peer on main
    john_node = nodes_by_id[person_john_main.get_id()]
    assert john_node.uuid == person_john_main.get_id()
    assert john_node.kind == "TestPerson"
    assert john_node.action is DiffAction.UPDATED
    assert john_node.is_node_kind_migration is False
    assert len(john_node.attributes) == 0
    assert len(john_node.relationships) == 1
    relationship_diff = john_node.relationships[0]
    assert relationship_diff.name == "cars"
    assert relationship_diff.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in relationship_diff.relationships}
    assert set(elements_by_peer_id.keys()) == {car_accord_main.get_id()}
    single_relationship = relationship_diff.relationships[0]
    assert single_relationship.peer_id == car_accord_main.id
    assert single_relationship.action is DiffAction.REMOVED
    properties_by_type = {p.property_type: p for p in single_relationship.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    assert {(p.property_type, p.action, p.previous_value, p.new_value) for p in single_relationship.properties} == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.REMOVED, car_accord_main.id, None),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.REMOVED, False, None),
    }
    for prop_diff in single_relationship.properties:
        assert before_main_change < prop_diff.changed_at < after_main_change


async def test_relationship_one_property_branch_update(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_jane_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    await car_main.owner.update(db=db, data={"id": person_jane_main.id})
    before_main_change = Timestamp()
    await car_main.save(db=db)
    after_main_change = Timestamp()
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await car_branch.owner.update(db=db, data={"id": person_john_main.id, "_relation__is_protected": True})
    before_branch_change = Timestamp()
    await car_branch.save(db=db)
    after_branch_change = Timestamp()

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    nodes_by_id = {n.uuid: n for n in branch_root_path.nodes}
    assert set(nodes_by_id.keys()) == {car_accord_main.id, person_john_main.id}
    # check relationship property on car node on branch
    car_node = nodes_by_id[car_main.get_id()]
    assert car_node.uuid == car_accord_main.id
    assert car_node.kind == "TestCar"
    assert car_node.action is DiffAction.UPDATED
    assert car_node.is_node_kind_migration is False
    assert len(car_node.attributes) == 0
    assert len(car_node.relationships) == 1
    relationship_diff = car_node.relationships[0]
    assert relationship_diff.name == "owner"
    assert relationship_diff.action is DiffAction.UPDATED
    assert len(relationship_diff.relationships) == 1
    single_relationship = relationship_diff.relationships[0]
    assert single_relationship.peer_id == person_john_main.id
    assert single_relationship.action is DiffAction.UPDATED
    assert len(single_relationship.properties) == 2
    property_diff_by_type = {p.property_type: p for p in single_relationship.properties}
    property_diff = property_diff_by_type[DatabaseEdgeType.IS_PROTECTED]
    assert property_diff.property_type == DatabaseEdgeType.IS_PROTECTED
    assert property_diff.previous_value is False
    assert property_diff.new_value is True
    assert before_branch_change < property_diff.changed_at < after_branch_change
    property_diff = property_diff_by_type[DatabaseEdgeType.IS_RELATED]
    assert property_diff.property_type == DatabaseEdgeType.IS_RELATED
    assert property_diff.previous_value == person_john_main.id
    assert property_diff.new_value == person_john_main.id
    assert property_diff.action is DiffAction.UNCHANGED
    assert property_diff.changed_at < before_branch_change
    # check relationship property on person node on branch
    john_node = nodes_by_id[person_john_main.get_id()]
    assert john_node.uuid == person_john_main.get_id()
    assert john_node.kind == "TestPerson"
    assert john_node.action is DiffAction.UPDATED
    assert john_node.is_node_kind_migration is False
    assert len(john_node.attributes) == 0
    assert len(john_node.relationships) == 1
    relationship_diff = john_node.relationships[0]
    assert relationship_diff.name == "cars"
    assert relationship_diff.action is DiffAction.UPDATED
    assert len(relationship_diff.relationships) == 1
    single_relationship = relationship_diff.relationships[0]
    assert single_relationship.peer_id == car_main.get_id()
    assert single_relationship.action is DiffAction.UPDATED
    assert len(single_relationship.properties) == 2
    property_diff_by_type = {p.property_type: p for p in single_relationship.properties}
    property_diff = property_diff_by_type[DatabaseEdgeType.IS_PROTECTED]
    assert property_diff.property_type == DatabaseEdgeType.IS_PROTECTED
    assert property_diff.previous_value is False
    assert property_diff.new_value is True
    assert before_branch_change < property_diff.changed_at < after_branch_change
    property_diff = property_diff_by_type[DatabaseEdgeType.IS_RELATED]
    assert property_diff.property_type == DatabaseEdgeType.IS_RELATED
    assert property_diff.previous_value == car_main.get_id()
    assert property_diff.new_value == car_main.get_id()
    assert property_diff.action is DiffAction.UNCHANGED
    assert property_diff.changed_at < before_branch_change
    # check relationship peer on new peer on main
    root_main_path = calculated_diffs.base_branch_diff
    assert root_main_path.branch == default_branch.name
    diff_nodes_by_id = {n.uuid: n for n in root_main_path.nodes}
    assert set(diff_nodes_by_id.keys()) == {person_john_main.id, car_accord_main.id}
    # check relationship peer on old peer on main
    node_diff = diff_nodes_by_id[person_john_main.id]
    assert node_diff.uuid == person_john_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 0
    assert len(node_diff.relationships) == 1
    relationship_diff = node_diff.relationships[0]
    assert relationship_diff.name == "cars"
    assert relationship_diff.action is DiffAction.UPDATED
    assert len(relationship_diff.relationships) == 1
    single_relationship_diff = relationship_diff.relationships[0]
    assert single_relationship_diff.peer_id == car_accord_main.id
    assert single_relationship_diff.action is DiffAction.REMOVED
    # check relationship peer on car on main
    node_diff = diff_nodes_by_id[car_accord_main.id]
    assert node_diff.uuid == car_accord_main.id
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 0
    assert len(node_diff.relationships) == 1
    relationship_diff = node_diff.relationships[0]
    assert relationship_diff.name == "owner"
    assert relationship_diff.action is DiffAction.UPDATED
    assert len(relationship_diff.relationships) == 2
    single_relationships_by_peer_id = {sr.peer_id: sr for sr in relationship_diff.relationships}
    single_relationship = single_relationships_by_peer_id[person_jane_main.id]
    assert single_relationship.peer_id == person_jane_main.id
    assert single_relationship.action is DiffAction.ADDED
    assert len(single_relationship.properties) == 2
    assert before_main_change < single_relationship.changed_at < after_main_change
    property_diff_by_type = {p.property_type: p for p in single_relationship.properties}
    property_diff = property_diff_by_type[DatabaseEdgeType.IS_RELATED]
    assert property_diff.property_type == DatabaseEdgeType.IS_RELATED
    assert property_diff.previous_value is None
    assert property_diff.new_value == person_jane_main.id
    assert property_diff.action is DiffAction.ADDED
    assert before_main_change < property_diff.changed_at < after_main_change
    property_diff = property_diff_by_type[DatabaseEdgeType.IS_PROTECTED]
    assert property_diff.property_type == DatabaseEdgeType.IS_PROTECTED
    assert property_diff.previous_value is None
    assert property_diff.new_value is False
    assert property_diff.action is DiffAction.ADDED
    assert before_main_change < property_diff.changed_at < after_main_change
    single_relationship = single_relationships_by_peer_id[person_john_main.id]
    assert single_relationship.peer_id == person_john_main.id
    assert single_relationship.action is DiffAction.REMOVED
    assert len(single_relationship.properties) == 2
    assert before_main_change < single_relationship.changed_at < after_main_change
    property_diff_by_type = {p.property_type: p for p in single_relationship.properties}
    property_diff = property_diff_by_type[DatabaseEdgeType.IS_RELATED]
    assert property_diff.property_type == DatabaseEdgeType.IS_RELATED
    assert property_diff.previous_value == person_john_main.id
    assert property_diff.new_value is None
    assert property_diff.action is DiffAction.REMOVED
    assert before_main_change < property_diff.changed_at < after_main_change
    property_diff = property_diff_by_type[DatabaseEdgeType.IS_PROTECTED]
    assert property_diff.property_type == DatabaseEdgeType.IS_PROTECTED
    assert property_diff.previous_value is False
    assert property_diff.new_value is None
    assert property_diff.action is DiffAction.REMOVED
    assert before_main_change < property_diff.changed_at < after_main_change


async def test_many_relationship_property_update(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    branch_car = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await branch_car.owner.update(db=db, data={"id": person_john_main.id, "_relation__source": person_jane_main.id})
    await branch_car.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.nodes == []
    root_path = calculated_diffs.diff_branch_diff
    assert root_path.branch == branch.name
    nodes_by_id = {n.uuid: n for n in root_path.nodes}
    assert set(nodes_by_id.keys()) == {person_john_main.get_id(), car_accord_main.get_id()}
    john_node = nodes_by_id[person_john_main.get_id()]
    assert john_node.action is DiffAction.UPDATED
    assert john_node.is_node_kind_migration is False
    assert john_node.attributes == []
    assert len(john_node.relationships) == 1
    cars_rel = john_node.relationships.pop()
    assert cars_rel.name == "cars"
    assert cars_rel.action is DiffAction.UPDATED
    assert len(cars_rel.relationships) == 1
    cars_element = cars_rel.relationships.pop()
    assert cars_element.action is DiffAction.UPDATED
    assert cars_element.peer_id == car_accord_main.get_id()
    properties_by_type = {p.property_type: p for p in cars_element.properties}
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.HAS_SOURCE}
    is_related_rel = properties_by_type[DatabaseEdgeType.IS_RELATED]
    assert is_related_rel.action is DiffAction.UNCHANGED
    assert is_related_rel.previous_value == car_accord_main.get_id()
    assert is_related_rel.new_value == car_accord_main.get_id()
    source_rel = properties_by_type[DatabaseEdgeType.HAS_SOURCE]
    assert source_rel.action is DiffAction.ADDED
    assert source_rel.previous_value is None
    assert source_rel.new_value == person_jane_main.get_id()
    car_node = nodes_by_id[car_accord_main.get_id()]
    assert car_node.action is DiffAction.UPDATED
    assert car_node.attributes == []
    assert len(car_node.relationships) == 1
    owner_rel = car_node.relationships.pop()
    assert owner_rel.name == "owner"
    assert owner_rel.action is DiffAction.UPDATED
    assert len(owner_rel.relationships) == 1
    owner_element = owner_rel.relationships.pop()
    assert owner_element.action is DiffAction.UPDATED
    assert owner_element.peer_id == person_john_main.get_id()
    properties_by_type = {p.property_type: p for p in owner_element.properties}
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.HAS_SOURCE}
    is_related_rel = properties_by_type[DatabaseEdgeType.IS_RELATED]
    assert is_related_rel.action is DiffAction.UNCHANGED
    assert is_related_rel.previous_value == person_john_main.get_id()
    assert is_related_rel.new_value == person_john_main.get_id()
    source_rel = properties_by_type[DatabaseEdgeType.HAS_SOURCE]
    assert source_rel.action is DiffAction.ADDED
    assert source_rel.previous_value is None
    assert source_rel.new_value == person_jane_main.get_id()


async def test_cardinality_one_peer_conflicting_updates(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    person_jane_main: Node,
    person_albert_main: Node,
    car_accord_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    branch_car = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await branch_car.owner.update(db=db, data={"id": person_albert_main.id})
    await branch_car.save(db=db)
    branch_update_done = Timestamp()
    main_car = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    await main_car.owner.update(db=db, data={"id": person_jane_main.id})
    await main_car.save(db=db)
    main_update_done = Timestamp()

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    # check branch
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 3
    nodes_by_id = {n.uuid: n for n in branch_root_path.nodes}
    assert set(nodes_by_id.keys()) == {car_accord_main.get_id(), person_john_main.get_id(), person_albert_main.get_id()}
    # check car node on branch
    car_node = nodes_by_id[car_accord_main.id]
    assert car_node.action is DiffAction.UPDATED
    assert car_node.is_node_kind_migration is False
    assert car_node.changed_at < from_time
    assert car_node.attributes == []
    assert len(car_node.relationships) == 1
    owner_rel = car_node.relationships[0]
    assert owner_rel.name == "owner"
    assert owner_rel.action is DiffAction.UPDATED
    assert from_time < owner_rel.changed_at < branch_update_done
    elements_by_id = {e.peer_id: e for e in owner_rel.relationships}
    assert set(elements_by_id.keys()) == {person_john_main.id, person_albert_main.id}
    # check john removed
    john_element = elements_by_id[person_john_main.id]
    assert john_element.action is DiffAction.REMOVED
    assert from_time < john_element.changed_at < branch_update_done
    properties_by_type = {p.property_type: p for p in john_element.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in [
        (DatabaseEdgeType.IS_RELATED, person_john_main.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.previous_value == previous_value
        assert diff_prop.new_value is None
        assert from_time < diff_prop.changed_at < branch_update_done
    # check albert added
    albert_element = elements_by_id[person_albert_main.id]
    assert albert_element.action is DiffAction.ADDED
    assert from_time < albert_element.changed_at < branch_update_done
    properties_by_type = {p.property_type: p for p in albert_element.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in [
        (DatabaseEdgeType.IS_RELATED, person_albert_main.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.previous_value is None
        assert diff_prop.new_value == new_value
        assert from_time < diff_prop.changed_at < branch_update_done
    # check john node on branch
    john_node = nodes_by_id[person_john_main.id]
    assert john_node.action is DiffAction.UPDATED
    assert john_node.is_node_kind_migration is False
    assert john_node.attributes == []
    assert len(john_node.relationships) == 1
    assert john_node.changed_at < from_time
    cars_rel = john_node.relationships.pop()
    assert cars_rel.name == "cars"
    assert cars_rel.action is DiffAction.UPDATED
    assert from_time < cars_rel.changed_at < branch_update_done
    assert len(cars_rel.relationships) == 1
    cars_element = cars_rel.relationships.pop()
    assert cars_element.peer_id == car_accord_main.id
    assert cars_element.action is DiffAction.REMOVED
    assert from_time < cars_element.changed_at < branch_update_done
    properties_by_type = {p.property_type: p for p in cars_element.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in [
        (DatabaseEdgeType.IS_RELATED, car_accord_main.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.previous_value == previous_value
        assert diff_prop.new_value is None
        assert from_time < diff_prop.changed_at < branch_update_done
    # check albert node on branch
    albert_node = nodes_by_id[person_albert_main.id]
    assert albert_node.action is DiffAction.UPDATED
    assert albert_node.is_node_kind_migration is False
    assert albert_node.attributes == []
    assert len(albert_node.relationships) == 1
    assert albert_node.changed_at < from_time
    cars_rel = albert_node.relationships.pop()
    assert cars_rel.name == "cars"
    assert cars_rel.action is DiffAction.UPDATED
    assert from_time < cars_rel.changed_at < branch_update_done
    assert len(cars_rel.relationships) == 1
    cars_element = cars_rel.relationships.pop()
    assert cars_element.peer_id == car_accord_main.id
    assert cars_element.action is DiffAction.ADDED
    assert from_time < cars_element.changed_at < branch_update_done
    properties_by_type = {p.property_type: p for p in cars_element.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in [
        (DatabaseEdgeType.IS_RELATED, car_accord_main.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.previous_value is None
        assert diff_prop.new_value == new_value
        assert from_time < diff_prop.changed_at < branch_update_done
    # check main
    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.branch == default_branch.name
    assert len(base_root_path.nodes) == 2
    nodes_by_id = {n.uuid: n for n in base_root_path.nodes}
    assert set(nodes_by_id.keys()) == {car_accord_main.get_id(), person_john_main.get_id()}
    # check car node on main
    car_node = nodes_by_id[car_accord_main.id]
    assert car_node.action is DiffAction.UPDATED
    assert car_node.changed_at < from_time
    assert car_node.is_node_kind_migration is False
    assert car_node.attributes == []
    assert len(car_node.relationships) == 1
    owner_rel = car_node.relationships[0]
    assert owner_rel.name == "owner"
    assert owner_rel.action is DiffAction.UPDATED
    assert branch_update_done < owner_rel.changed_at < main_update_done
    elements_by_id = {e.peer_id: e for e in owner_rel.relationships}
    assert set(elements_by_id.keys()) == {person_john_main.id, person_jane_main.id}
    # check john removed
    john_element = elements_by_id[person_john_main.id]
    assert john_element.action is DiffAction.REMOVED
    assert branch_update_done < john_element.changed_at < main_update_done
    properties_by_type = {p.property_type: p for p in john_element.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in [
        (DatabaseEdgeType.IS_RELATED, person_john_main.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.previous_value == previous_value
        assert diff_prop.new_value is None
        assert branch_update_done < diff_prop.changed_at < main_update_done
    # check jane added
    jane_element = elements_by_id[person_jane_main.id]
    assert jane_element.action is DiffAction.ADDED
    assert branch_update_done < jane_element.changed_at < main_update_done
    properties_by_type = {p.property_type: p for p in jane_element.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in [
        (DatabaseEdgeType.IS_RELATED, person_jane_main.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.previous_value is None
        assert diff_prop.new_value == new_value
        assert branch_update_done < diff_prop.changed_at < main_update_done
    # check john node on main
    john_node = nodes_by_id[person_john_main.id]
    assert john_node.action is DiffAction.UPDATED
    assert john_node.is_node_kind_migration is False
    assert john_node.attributes == []
    assert len(john_node.relationships) == 1
    assert john_node.changed_at < from_time
    cars_rel = john_node.relationships.pop()
    assert cars_rel.name == "cars"
    assert cars_rel.action is DiffAction.UPDATED
    assert branch_update_done < cars_rel.changed_at < main_update_done
    assert len(cars_rel.relationships) == 1
    cars_element = cars_rel.relationships.pop()
    assert cars_element.peer_id == car_accord_main.id
    assert cars_element.action is DiffAction.REMOVED
    assert branch_update_done < cars_element.changed_at < main_update_done
    properties_by_type = {p.property_type: p for p in cars_element.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in [
        (DatabaseEdgeType.IS_RELATED, car_accord_main.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.previous_value == previous_value
        assert diff_prop.new_value is None
        assert branch_update_done < diff_prop.changed_at < main_update_done


async def test_relationship_property_owner_conflicting_updates(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    main_john = await NodeManager.get_one(db=db, branch=default_branch, id=person_john_main.id)
    await main_john.cars.update(db=db, data={"id": car_accord_main.id, "_relation__owner": person_john_main.id})
    await main_john.save(db=db)
    branch_john = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
    await branch_john.cars.update(db=db, data={"id": car_accord_main.id, "_relation__owner": car_accord_main.id})
    await branch_john.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    # check branch
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    nodes_by_id = {n.uuid: n for n in branch_root_path.nodes}
    assert set(nodes_by_id.keys()) == {person_john_main.get_id(), car_accord_main.get_id()}
    # john node on branch
    john_node = nodes_by_id[person_john_main.get_id()]
    assert john_node.action is DiffAction.UPDATED
    assert john_node.is_node_kind_migration is False
    assert john_node.attributes == []
    assert len(john_node.relationships) == 1
    cars_rel = john_node.relationships.pop()
    assert cars_rel.name == "cars"
    assert cars_rel.action is DiffAction.UPDATED
    assert len(cars_rel.relationships) == 1
    cars_element = cars_rel.relationships.pop()
    assert cars_element.action is DiffAction.UPDATED
    assert cars_element.peer_id == car_accord_main.get_id()
    properties_by_type = {p.property_type: p for p in cars_element.properties}
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.HAS_OWNER}
    is_related_rel = properties_by_type[DatabaseEdgeType.IS_RELATED]
    assert is_related_rel.action is DiffAction.UNCHANGED
    assert is_related_rel.previous_value == car_accord_main.get_id()
    assert is_related_rel.new_value == car_accord_main.get_id()
    owner_rel = properties_by_type[DatabaseEdgeType.HAS_OWNER]
    assert owner_rel.action is DiffAction.ADDED
    assert owner_rel.previous_value is None
    assert owner_rel.new_value == car_accord_main.get_id()
    # car node on branch
    car_node = nodes_by_id[car_accord_main.get_id()]
    assert car_node.action is DiffAction.UPDATED
    assert car_node.is_node_kind_migration is False
    assert car_node.attributes == []
    assert len(car_node.relationships) == 1
    owner_rel = car_node.relationships.pop()
    assert owner_rel.name == "owner"
    assert owner_rel.action is DiffAction.UPDATED
    assert len(owner_rel.relationships) == 1
    owner_element = owner_rel.relationships.pop()
    assert owner_element.action is DiffAction.UPDATED
    assert owner_element.peer_id == person_john_main.get_id()
    properties_by_type = {p.property_type: p for p in owner_element.properties}
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.HAS_OWNER}
    is_related_rel = properties_by_type[DatabaseEdgeType.IS_RELATED]
    assert is_related_rel.action is DiffAction.UNCHANGED
    assert is_related_rel.previous_value == person_john_main.get_id()
    assert is_related_rel.new_value == person_john_main.get_id()
    owner_rel = properties_by_type[DatabaseEdgeType.HAS_OWNER]
    assert owner_rel.action is DiffAction.ADDED
    assert owner_rel.previous_value is None
    assert owner_rel.new_value == car_accord_main.get_id()
    # check main
    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.branch == default_branch.name
    assert len(base_root_path.nodes) == 2
    nodes_by_id = {n.uuid: n for n in base_root_path.nodes}
    assert set(nodes_by_id.keys()) == {person_john_main.get_id(), car_accord_main.get_id()}
    # john node on main
    john_node = nodes_by_id[person_john_main.get_id()]
    assert john_node.action is DiffAction.UPDATED
    assert john_node.is_node_kind_migration is False
    assert john_node.attributes == []
    assert len(john_node.relationships) == 1
    cars_rel = john_node.relationships.pop()
    assert cars_rel.name == "cars"
    assert cars_rel.action is DiffAction.UPDATED
    assert len(cars_rel.relationships) == 1
    cars_element = cars_rel.relationships.pop()
    assert cars_element.action is DiffAction.UPDATED
    assert cars_element.peer_id == car_accord_main.get_id()
    properties_by_type = {p.property_type: p for p in cars_element.properties}
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.HAS_OWNER}
    is_related_rel = properties_by_type[DatabaseEdgeType.IS_RELATED]
    assert is_related_rel.action is DiffAction.UNCHANGED
    assert is_related_rel.previous_value == car_accord_main.get_id()
    assert is_related_rel.new_value == car_accord_main.get_id()
    owner_rel = properties_by_type[DatabaseEdgeType.HAS_OWNER]
    assert owner_rel.action is DiffAction.ADDED
    assert owner_rel.previous_value is None
    assert owner_rel.new_value == person_john_main.get_id()
    # car node on main
    car_node = nodes_by_id[car_accord_main.get_id()]
    assert car_node.action is DiffAction.UPDATED
    assert car_node.is_node_kind_migration is False
    assert car_node.attributes == []
    assert len(car_node.relationships) == 1
    owner_rel = car_node.relationships.pop()
    assert owner_rel.name == "owner"
    assert owner_rel.action is DiffAction.UPDATED
    assert len(owner_rel.relationships) == 1
    owner_element = owner_rel.relationships.pop()
    assert owner_element.action is DiffAction.UPDATED
    assert owner_element.peer_id == person_john_main.get_id()
    properties_by_type = {p.property_type: p for p in owner_element.properties}
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.HAS_OWNER}
    is_related_rel = properties_by_type[DatabaseEdgeType.IS_RELATED]
    assert is_related_rel.action is DiffAction.UNCHANGED
    assert is_related_rel.previous_value == person_john_main.get_id()
    assert is_related_rel.new_value == person_john_main.get_id()
    owner_rel = properties_by_type[DatabaseEdgeType.HAS_OWNER]
    assert owner_rel.action is DiffAction.ADDED
    assert owner_rel.previous_value is None
    assert owner_rel.new_value == person_john_main.get_id()


async def test_agnostic_source_relationship_update(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_global: None,
) -> None:
    person_1 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person_1.new(db=db, name="Herb", height=165)
    await person_1.save(db=db)
    new_car = await Node.init(db=db, branch=default_branch, schema="TestCar")
    await new_car.new(db=db, name="Batmobile", color="#000000", nbr_seats=1, is_electric=False, owner=person_1)
    await new_car.save(db=db)
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    branch_car = await NodeManager.get_one(db=db, branch=branch, id=new_car.id)
    await branch_car.owner.update(db=db, data={"id": person_1.id, "_relation__source": person_1.id})
    await branch_car.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.nodes == []
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    # The HAS_SOURCE addition on the IS_RELATED edge surfaces under both endpoints:
    # the AWARE Car (via its `owner` relationship) and the AGNOSTIC Person (via its
    # inverse `cars` relationship).
    diff_nodes_by_id = {n.uuid: n for n in branch_root_path.nodes}
    assert set(diff_nodes_by_id.keys()) == {new_car.get_id(), person_1.get_id()}

    diff_node_car = diff_nodes_by_id[new_car.get_id()]
    assert diff_node_car.action is DiffAction.UPDATED
    assert diff_node_car.is_node_kind_migration is False
    assert diff_node_car.attributes == []
    assert len(diff_node_car.relationships) == 1
    diff_relationship_owner = diff_node_car.relationships[0]
    assert diff_relationship_owner.name == "owner"
    assert diff_relationship_owner.action is DiffAction.UPDATED
    assert len(diff_relationship_owner.relationships) == 1
    diff_element_owner = diff_relationship_owner.relationships[0]
    assert diff_element_owner.peer_id == person_1.get_id()
    assert diff_element_owner.action is DiffAction.UPDATED
    owner_props_by_type = {p.property_type: p for p in diff_element_owner.properties}
    assert set(owner_props_by_type.keys()) == {DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.HAS_SOURCE}
    owner_is_related = owner_props_by_type[DatabaseEdgeType.IS_RELATED]
    assert owner_is_related.previous_value == person_1.get_id()
    assert owner_is_related.new_value == person_1.get_id()
    assert owner_is_related.action is DiffAction.UNCHANGED
    owner_has_source = owner_props_by_type[DatabaseEdgeType.HAS_SOURCE]
    assert owner_has_source.previous_value is None
    assert owner_has_source.new_value == person_1.get_id()
    assert owner_has_source.action is DiffAction.ADDED

    diff_node_person = diff_nodes_by_id[person_1.get_id()]
    assert diff_node_person.action is DiffAction.UPDATED
    assert diff_node_person.is_node_kind_migration is False
    assert diff_node_person.attributes == []
    assert len(diff_node_person.relationships) == 1
    diff_relationship_cars = diff_node_person.relationships[0]
    assert diff_relationship_cars.name == "cars"
    assert diff_relationship_cars.action is DiffAction.UPDATED
    assert len(diff_relationship_cars.relationships) == 1
    diff_element_cars = diff_relationship_cars.relationships[0]
    assert diff_element_cars.peer_id == new_car.get_id()
    assert diff_element_cars.action is DiffAction.UPDATED
    cars_props_by_type = {p.property_type: p for p in diff_element_cars.properties}
    assert set(cars_props_by_type.keys()) == {DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.HAS_SOURCE}
    cars_is_related = cars_props_by_type[DatabaseEdgeType.IS_RELATED]
    assert cars_is_related.previous_value == new_car.get_id()
    assert cars_is_related.new_value == new_car.get_id()
    assert cars_is_related.action is DiffAction.UNCHANGED
    cars_has_source = cars_props_by_type[DatabaseEdgeType.HAS_SOURCE]
    assert cars_has_source.previous_value is None
    assert cars_has_source.new_value == person_1.get_id()
    assert cars_has_source.action is DiffAction.ADDED


async def test_agnostic_owner_relationship_added(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_global: None,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    person_1 = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person_1.new(db=db, name="Herb", height=165)
    await person_1.save(db=db)
    new_car = await Node.init(db=db, branch=branch, schema="TestCar")
    await new_car.new(db=db, name="Batmobile", color="#000000", nbr_seats=1, is_electric=False, owner=person_1)
    await new_car.owner.update(db=db, data={"id": person_1.id, "_relation__owner": person_1.id})
    await new_car.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.nodes == []
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    diff_nodes_by_id = {n.uuid: n for n in branch_root_path.nodes}
    assert set(diff_nodes_by_id.keys()) == {new_car.get_id(), person_1.get_id()}
    diff_node_car = diff_nodes_by_id[new_car.get_id()]
    assert diff_node_car.is_node_kind_migration is False
    assert diff_node_car.action is DiffAction.ADDED
    assert {(attr.name, attr.action) for attr in diff_node_car.attributes} == {
        ("human_friendly_id", DiffAction.ADDED),
        ("display_label", DiffAction.ADDED),
        ("name", DiffAction.ADDED),
        ("color", DiffAction.ADDED),
        ("is_electric", DiffAction.ADDED),
    }
    assert len(diff_node_car.relationships) == 1
    diff_relationship = diff_node_car.relationships.pop()
    assert diff_relationship.name == "owner"
    assert diff_relationship.action is DiffAction.ADDED
    assert len(diff_relationship.relationships) == 1
    diff_element = diff_relationship.relationships.pop()
    assert diff_element.peer_id == person_1.get_id()
    assert diff_element.action is DiffAction.ADDED
    diff_props_by_type = {p.property_type: p for p in diff_element.properties}
    assert set(diff_props_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.HAS_OWNER,
        DatabaseEdgeType.IS_PROTECTED,
    }
    diff_prop_tuples = {
        (diff_prop.property_type, diff_prop.action, diff_prop.previous_value, diff_prop.new_value)
        for diff_prop in diff_props_by_type.values()
    }
    assert diff_prop_tuples == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.ADDED, None, person_1.get_id()),
        (DatabaseEdgeType.HAS_OWNER, DiffAction.ADDED, None, person_1.get_id()),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.ADDED, None, False),
    }
    diff_node_person = diff_nodes_by_id[person_1.get_id()]
    assert diff_node_person.action is DiffAction.UPDATED
    assert diff_node_person.is_node_kind_migration is False
    assert len(diff_node_person.attributes) == 0
    assert len(diff_node_person.relationships) == 1
    diff_relationship = diff_node_person.relationships.pop()
    assert diff_relationship.name == "cars"
    assert diff_relationship.action is DiffAction.UPDATED
    assert len(diff_relationship.relationships) == 1
    diff_element = diff_relationship.relationships.pop()
    assert diff_element.peer_id == new_car.get_id()
    assert diff_element.action is DiffAction.ADDED

    diff_props_by_type = {p.property_type: p for p in diff_element.properties}
    assert set(diff_props_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.HAS_OWNER,
        DatabaseEdgeType.IS_PROTECTED,
    }
    diff_prop_tuples = {
        (diff_prop.property_type, diff_prop.action, diff_prop.previous_value, diff_prop.new_value)
        for diff_prop in diff_props_by_type.values()
    }
    assert diff_prop_tuples == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.ADDED, None, new_car.get_id()),
        (DatabaseEdgeType.HAS_OWNER, DiffAction.ADDED, None, person_1.get_id()),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.ADDED, None, False),
    }


async def test_hierarchy_with_same_kind_parent_and_child(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
) -> None:
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix")
    ip_namespace = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ip_namespace.new(db=db, name="ns1")
    await ip_namespace.save(db=db)
    top_node = await Node.init(db=db, schema=prefix_schema)
    await top_node.new(db=db, prefix="10.0.0.0/7", ip_namespace=ip_namespace)
    await top_node.save(db=db)
    mid_node = await Node.init(db=db, schema=prefix_schema)
    await mid_node.new(db=db, prefix="10.0.0.0/8", ip_namespace=ip_namespace)
    await mid_node.save(db=db)
    bottom_node = await Node.init(db=db, schema=prefix_schema)
    await bottom_node.new(db=db, prefix="10.0.0.0/9", ip_namespace=ip_namespace)
    await bottom_node.save(db=db)
    branch = await create_branch(db=db, branch_name="branch2")
    from_time = Timestamp()
    mid_branch = await NodeManager.get_one(db=db, branch=branch, id=mid_node.id)
    await mid_branch.parent.update(db=db, data=top_node.id)
    await mid_branch.save(db=db)
    bottom_branch = await NodeManager.get_one(db=db, branch=branch, id=bottom_node.id)
    await bottom_branch.parent.update(db=db, data=mid_node.id)
    await bottom_branch.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    nodes_by_id = {n.uuid: n for n in branch_root_path.nodes}
    assert set(nodes_by_id.keys()) == {top_node.id, mid_node.id, bottom_node.id}
    # top node
    node_diff = nodes_by_id[top_node.id]
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 0
    rels_by_name = {r.name: r for r in node_diff.relationships}
    assert set(rels_by_name.keys()) == {"children"}
    children_rel = rels_by_name["children"]
    assert children_rel.action is DiffAction.UPDATED
    assert len(children_rel.relationships) == 1
    child_element = children_rel.relationships[0]
    assert child_element.action is DiffAction.ADDED
    assert child_element.peer_id == mid_node.id
    properties_by_type = {p.property_type: p for p in child_element.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_RELATED, mid_node.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.action is DiffAction.ADDED
        assert diff_prop.previous_value is None
        assert diff_prop.new_value == new_value

    # middle node
    node_diff = nodes_by_id[mid_node.id]
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 0
    rels_by_name = {r.name: r for r in node_diff.relationships}
    assert set(rels_by_name.keys()) == {"parent", "children"}
    parent_rel = rels_by_name["parent"]
    assert parent_rel.action is DiffAction.ADDED
    assert len(parent_rel.relationships) == 1
    parent_element = parent_rel.relationships[0]
    assert parent_element.action is DiffAction.ADDED
    assert parent_element.peer_id == top_node.id
    properties_by_type = {p.property_type: p for p in parent_element.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_RELATED, top_node.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.action is DiffAction.ADDED
        assert diff_prop.previous_value is None
        assert diff_prop.new_value == new_value
    children_rel = rels_by_name["children"]
    assert children_rel.action is DiffAction.UPDATED
    assert len(children_rel.relationships) == 1
    child_element = children_rel.relationships[0]
    assert child_element.action is DiffAction.ADDED
    assert child_element.peer_id == bottom_node.id
    properties_by_type = {p.property_type: p for p in child_element.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_RELATED, bottom_node.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.action is DiffAction.ADDED
        assert diff_prop.previous_value is None
        assert diff_prop.new_value == new_value

    # bottom node
    node_diff = nodes_by_id[bottom_node.id]
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 0
    rels_by_name = {r.name: r for r in node_diff.relationships}
    assert set(rels_by_name.keys()) == {"parent"}
    parent_rel = rels_by_name["parent"]
    assert parent_rel.action is DiffAction.ADDED
    assert len(parent_rel.relationships) == 1
    parent_element = parent_rel.relationships[0]
    assert parent_element.action is DiffAction.ADDED
    assert parent_element.peer_id == mid_node.id
    properties_by_type = {p.property_type: p for p in parent_element.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_RELATED, mid_node.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.action is DiffAction.ADDED
        assert diff_prop.previous_value is None
        assert diff_prop.new_value == new_value


async def test_diff_relationship_update_includes_unchanged_properties(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp()
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await car_branch.owner.update(db=db, data=person_alfred_main)
    await car_branch.save(db=db)

    diff_calculator = DiffCalculator(db=db)

    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=True,
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.branch == default_branch.name
    assert len(base_root_path.nodes) == 0
    nodes_by_id = {n.uuid: n for n in base_root_path.nodes}

    branch_diff_path = calculated_diffs.diff_branch_diff
    assert branch_diff_path.branch == branch.name
    nodes_by_id = {n.uuid: n for n in branch_diff_path.nodes}
    assert set(nodes_by_id.keys()) == {car_accord_main.id, person_john_main.id, person_alfred_main.id}
    # car on branch
    node_diff = nodes_by_id[car_accord_main.id]
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 0
    assert len(node_diff.relationships) == 1
    diff_rel = node_diff.relationships.pop()
    assert diff_rel.name == "owner"
    assert diff_rel.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in diff_rel.relationships}
    assert set(elements_by_peer_id.keys()) == {person_john_main.id, person_alfred_main.id}
    alfred_owner_diff = elements_by_peer_id[person_alfred_main.id]
    properties_by_type = {p.property_type: p for p in alfred_owner_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    related_prop = properties_by_type[DatabaseEdgeType.IS_RELATED]
    assert related_prop.action is DiffAction.ADDED
    assert related_prop.previous_value is None
    assert related_prop.new_value == person_alfred_main.id
    prop_type, value = (DatabaseEdgeType.IS_PROTECTED, False)
    prop_diff = properties_by_type[prop_type]
    assert prop_diff.action is DiffAction.ADDED
    assert prop_diff.previous_value is None
    assert prop_diff.new_value == value
    # john on branch
    node_diff = nodes_by_id[person_john_main.id]
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 0
    assert len(node_diff.relationships) == 1
    diff_rel = node_diff.relationships.pop()
    assert diff_rel.name == "cars"
    assert diff_rel.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in diff_rel.relationships}
    assert set(elements_by_peer_id.keys()) == {car_accord_main.id}
    accord_cars_diff = elements_by_peer_id[car_accord_main.id]
    properties_by_type = {p.property_type: p for p in accord_cars_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    related_prop = properties_by_type[DatabaseEdgeType.IS_RELATED]
    assert related_prop.action is DiffAction.REMOVED
    assert related_prop.previous_value == car_accord_main.id
    assert related_prop.new_value is None
    prop_type, value = (DatabaseEdgeType.IS_PROTECTED, False)
    prop_diff = properties_by_type[prop_type]
    assert prop_diff.action is DiffAction.REMOVED
    assert prop_diff.previous_value == value
    assert prop_diff.new_value is None
    # alfred on branch
    node_diff = nodes_by_id[person_alfred_main.id]
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 0
    assert len(node_diff.relationships) == 1
    diff_rel = node_diff.relationships.pop()
    assert diff_rel.name == "cars"
    assert diff_rel.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in diff_rel.relationships}
    assert set(elements_by_peer_id.keys()) == {car_accord_main.id}
    accord_cars_diff = elements_by_peer_id[car_accord_main.id]
    properties_by_type = {p.property_type: p for p in accord_cars_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    related_prop = properties_by_type[DatabaseEdgeType.IS_RELATED]
    assert related_prop.action is DiffAction.ADDED
    assert related_prop.previous_value is None
    assert related_prop.new_value == car_accord_main.id
    prop_type, value = (DatabaseEdgeType.IS_PROTECTED, False)
    prop_diff = properties_by_type[prop_type]
    assert prop_diff.action is DiffAction.ADDED
    assert prop_diff.previous_value is None
    assert prop_diff.new_value == value


async def test_diff_relationship_property_update_on_main(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    await car_main.owner.update(db=db, data=person_alfred_main)
    await car_main.save(db=db)

    from_time = Timestamp()
    car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    await car_main.owner.update(db=db, data=person_john_main)
    await car_main.save(db=db)
    car_schema = car_main.get_schema()
    owner_rel_schema = car_schema.get_relationship(name="owner")

    diff_calculator = DiffCalculator(db=db)
    node_field_specifiers = NodeFieldSpecifierMap()
    node_field_specifiers.add_entry(
        node_uuid=car_accord_main.id, kind=car_accord_main.get_kind(), field_name=owner_rel_schema.get_identifier()
    )
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        previous_node_specifiers=node_field_specifiers,
        include_unchanged=True,
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.branch == default_branch.name
    assert len(base_root_path.nodes) == 1
    nodes_by_id = {n.uuid: n for n in base_root_path.nodes}
    # car on main
    node_diff = nodes_by_id[car_accord_main.id]
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 0
    assert len(node_diff.relationships) == 1
    diff_rel = node_diff.relationships.pop()
    assert diff_rel.name == "owner"
    assert diff_rel.action is DiffAction.UPDATED
    assert {elem.action for elem in diff_rel.relationships} == {DiffAction.ADDED, DiffAction.REMOVED}
