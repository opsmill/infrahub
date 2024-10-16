import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.calculator import DiffCalculator
from infrahub.core.diff.model.path import NodeFieldSpecifier
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


async def test_diff_attribute_branch_update(
    db: InfrahubDatabase, default_branch: Branch, person_alfred_main, person_john_main, car_accord_main
):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    alfred_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_alfred_main.id)
    alfred_main.name.value = "Big Alfred"
    main_before_change = Timestamp()
    await alfred_main.save(db=db)
    main_after_change = Timestamp()
    alfred_branch = await NodeManager.get_one(db=db, branch=branch, id=person_alfred_main.id)
    alfred_branch.name.value = "Little Alfred"
    branch_before_change = Timestamp()
    await alfred_branch.save(db=db)
    branch_after_change = Timestamp()

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    main_root_path = calculated_diffs.base_branch_diff
    assert main_root_path.branch == default_branch.name
    assert len(main_root_path.nodes) == 1
    node_diff = main_root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Big Alfred"
    assert property_diff.action is DiffAction.UPDATED
    assert main_before_change < property_diff.changed_at < main_after_change
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    node_diff = branch_root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Little Alfred"
    assert property_diff.action is DiffAction.UPDATED
    assert branch_before_change < property_diff.changed_at < branch_after_change


async def test_attribute_property_main_update(
    db: InfrahubDatabase, default_branch: Branch, person_alfred_main, person_john_main, car_accord_main
):
    from_time = Timestamp()
    alfred_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_alfred_main.id)
    alfred_main.name.is_visible = False
    alfred_main.name.is_protected = True
    before_change = Timestamp()
    await alfred_main.save(db=db)
    after_change = Timestamp()

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=default_branch, from_time=from_time, to_time=Timestamp()
    )

    base_root_path = calculated_diffs.base_branch_diff
    main_root_path = calculated_diffs.diff_branch_diff
    assert base_root_path == main_root_path
    assert main_root_path.branch == default_branch.name
    assert len(main_root_path.nodes) == 1
    node_diff = main_root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 2
    properties_by_type = {p.property_type: p for p in attribute_diff.properties}
    property_diff = properties_by_type[DatabaseEdgeType.IS_VISIBLE]
    assert property_diff.property_type == DatabaseEdgeType.IS_VISIBLE
    assert property_diff.previous_value is True
    assert property_diff.new_value is False
    assert property_diff.action is DiffAction.UPDATED
    assert before_change < property_diff.changed_at < after_change
    property_diff = properties_by_type[DatabaseEdgeType.IS_PROTECTED]
    assert property_diff.property_type == DatabaseEdgeType.IS_PROTECTED
    assert property_diff.previous_value is False
    assert property_diff.new_value is True
    assert property_diff.action is DiffAction.UPDATED
    assert before_change < property_diff.changed_at < after_change


async def test_attribute_branch_set_null(db: InfrahubDatabase, default_branch: Branch, car_accord_main):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    car_branch.nbr_seats.value = None
    before_change = Timestamp()
    await car_branch.save(db=db)
    after_change = Timestamp()

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.nodes == []
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    node_diff = branch_root_path.nodes[0]
    assert node_diff.uuid == car_accord_main.id
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "nbr_seats"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == 5
    assert property_diff.new_value == "NULL"
    assert property_diff.action is DiffAction.REMOVED
    assert before_change < property_diff.changed_at < after_change


@pytest.mark.parametrize("use_branch", [True, False])
async def test_node_delete(db: InfrahubDatabase, default_branch: Branch, car_accord_main, person_john_main, use_branch):
    if use_branch:
        branch = await create_branch(db=db, branch_name="branch")
    else:
        branch = default_branch
    from_time = Timestamp()
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await car_branch.delete(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    base_root_path = calculated_diffs.base_branch_diff
    branch_root_path = calculated_diffs.diff_branch_diff
    if branch is default_branch:
        assert base_root_path == branch_root_path
    else:
        assert base_root_path.nodes == []
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 2
    node_diffs_by_id = {n.uuid: n for n in branch_root_path.nodes}
    node_diff = node_diffs_by_id[car_accord_main.id]
    assert node_diff.uuid == car_accord_main.id
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.REMOVED
    assert len(node_diff.attributes) == 5
    assert len(node_diff.relationships) == 1
    relationship_diff = node_diff.relationships[0]
    attributes_by_name = {attr.name: attr for attr in node_diff.attributes}
    assert set(attributes_by_name.keys()) == {"name", "nbr_seats", "color", "is_electric", "transmission"}
    for attribute_diff in attributes_by_name.values():
        assert attribute_diff.action is DiffAction.REMOVED
        properties_by_type = {prop.property_type: prop for prop in attribute_diff.properties}
        diff_property = properties_by_type[DatabaseEdgeType.HAS_VALUE]
        assert diff_property.action is DiffAction.REMOVED
        assert diff_property.new_value in (None, "NULL")
    assert len(node_diff.relationships) == 1
    relationship_diff = node_diff.relationships[0]
    assert relationship_diff.name == "owner"
    assert relationship_diff.action is DiffAction.REMOVED
    assert len(relationship_diff.relationships) == 1
    single_relationship_diff = relationship_diff.relationships[0]
    assert single_relationship_diff.peer_id == person_john_main.id
    assert single_relationship_diff.action is DiffAction.REMOVED
    node_diff = node_diffs_by_id[person_john_main.id]
    assert node_diff.uuid == person_john_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 0
    assert len(node_diff.relationships) == 1
    relationship_diff = node_diff.relationships[0]
    assert relationship_diff.name == "cars"
    assert relationship_diff.action is DiffAction.UPDATED
    assert len(relationship_diff.relationships) == 1
    single_relationship_diff = relationship_diff.relationships[0]
    assert single_relationship_diff.peer_id == car_branch.id
    assert single_relationship_diff.action is DiffAction.REMOVED
    assert len(single_relationship_diff.properties) == 3
    for diff_property in single_relationship_diff.properties:
        assert diff_property.action is DiffAction.REMOVED


async def test_node_base_delete_branch_update(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main, person_john_main
):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp()
    car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    await car_main.delete(db=db)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    car_branch.nbr_seats.value = 10
    await car_branch.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert len(base_root_path.nodes) == 1
    node_diffs_by_id = {n.uuid: n for n in base_root_path.nodes}
    node_diff = node_diffs_by_id[car_accord_main.id]
    assert node_diff.uuid == car_accord_main.id
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.REMOVED
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    node_diffs_by_id = {n.uuid: n for n in branch_root_path.nodes}
    node_diff = node_diffs_by_id[car_accord_main.id]
    assert node_diff.uuid == car_accord_main.id
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 1
    assert len(node_diff.relationships) == 0
    attributes_by_name = {attr.name: attr for attr in node_diff.attributes}
    assert set(attributes_by_name.keys()) == {"nbr_seats"}
    attribute_diff = attributes_by_name["nbr_seats"]
    assert attribute_diff.action is DiffAction.UPDATED
    properties_by_type = {prop.property_type: prop for prop in attribute_diff.properties}
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.HAS_VALUE}
    diff_property = properties_by_type[DatabaseEdgeType.HAS_VALUE]
    assert diff_property.action is DiffAction.UPDATED
    assert diff_property.previous_value == 5
    assert diff_property.new_value == 10


async def test_node_branch_add(db: InfrahubDatabase, default_branch: Branch, car_accord_main):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    new_person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await new_person.new(db=db, name="Stokely")
    before_change = Timestamp()
    await new_person.save(db=db)
    after_change = Timestamp()

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.nodes == []
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    node_diff = branch_root_path.nodes[0]
    assert node_diff.uuid == new_person.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.ADDED
    assert before_change < node_diff.changed_at < after_change
    attributes_by_name = {attr.name: attr for attr in node_diff.attributes}
    assert set(attributes_by_name.keys()) == {"name", "height"}
    attribute_diff = attributes_by_name["name"]
    assert attribute_diff.action is DiffAction.ADDED
    assert before_change < attribute_diff.changed_at < after_change
    properties_by_type = {prop.property_type: prop for prop in attribute_diff.properties}
    diff_property = properties_by_type[DatabaseEdgeType.HAS_VALUE]
    assert diff_property.action is DiffAction.ADDED
    assert diff_property.new_value == "Stokely"
    assert before_change < diff_property.changed_at < after_change


async def test_attribute_property_multiple_branch_updates(
    db: InfrahubDatabase, default_branch: Branch, person_alfred_main, person_john_main, car_accord_main
):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    alfred_branch = await NodeManager.get_one(db=db, branch=branch, id=person_alfred_main.id)
    alfred_branch.name.value = "Alfred Two"
    await alfred_branch.save(db=db)
    alfred_branch.name.value = "Alfred Three"
    await alfred_branch.save(db=db)
    before_last_change = Timestamp()
    alfred_branch.name.value = "Alfred Four"
    await alfred_branch.save(db=db)
    after_last_change = Timestamp()

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.nodes == []
    root_path = calculated_diffs.diff_branch_diff
    assert root_path.branch == branch.name
    assert len(root_path.nodes) == 1
    node_diff = root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Alfred Four"
    assert before_last_change < property_diff.changed_at < after_last_change


async def test_relationship_one_peer_branch_and_main_update(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main,
    person_jane_main,
    person_john_main,
    car_accord_main,
):
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
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
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
        DatabaseEdgeType.IS_VISIBLE,
    }
    assert {(p.property_type, p.action, p.previous_value, p.new_value) for p in removed_relationship.properties} == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.REMOVED, person_john_main.id, None),
        (DatabaseEdgeType.IS_VISIBLE, DiffAction.REMOVED, True, None),
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
        DatabaseEdgeType.IS_VISIBLE,
    }
    assert {(p.property_type, p.action, p.previous_value, p.new_value) for p in added_relationship.properties} == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.ADDED, None, person_alfred_main.id),
        (DatabaseEdgeType.IS_VISIBLE, DiffAction.ADDED, None, True),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.ADDED, None, False),
    }
    for prop_diff in added_relationship.properties:
        assert before_branch_change < prop_diff.changed_at < after_branch_change
    # check relationship on removed peer on branch
    john_node = nodes_by_id[person_john_main.get_id()]
    assert john_node.uuid == person_john_main.get_id()
    assert john_node.kind == "TestPerson"
    assert john_node.action is DiffAction.UPDATED
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
        DatabaseEdgeType.IS_VISIBLE,
    }
    assert {(p.property_type, p.action, p.previous_value, p.new_value) for p in single_relationship.properties} == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.REMOVED, car_accord_main.id, None),
        (DatabaseEdgeType.IS_VISIBLE, DiffAction.REMOVED, True, None),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.REMOVED, False, None),
    }
    for prop_diff in single_relationship.properties:
        assert before_branch_change < prop_diff.changed_at < after_branch_change
    # check relationship on added peer on branch
    alfred_node = nodes_by_id[person_alfred_main.get_id()]
    assert alfred_node.uuid == person_alfred_main.get_id()
    assert alfred_node.kind == "TestPerson"
    assert alfred_node.action is DiffAction.UPDATED
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
        DatabaseEdgeType.IS_VISIBLE,
    }
    assert {(p.property_type, p.action, p.previous_value, p.new_value) for p in single_relationship.properties} == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.ADDED, None, car_accord_main.id),
        (DatabaseEdgeType.IS_VISIBLE, DiffAction.ADDED, None, True),
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
        DatabaseEdgeType.IS_VISIBLE,
    }
    assert {(p.property_type, p.action, p.previous_value, p.new_value) for p in removed_relationship.properties} == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.REMOVED, person_john_main.id, None),
        (DatabaseEdgeType.IS_VISIBLE, DiffAction.REMOVED, True, None),
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
        DatabaseEdgeType.IS_VISIBLE,
    }
    assert {(p.property_type, p.action, p.previous_value, p.new_value) for p in added_relationship.properties} == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.ADDED, None, person_jane_main.id),
        (DatabaseEdgeType.IS_VISIBLE, DiffAction.ADDED, None, True),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.ADDED, None, False),
    }
    for prop_diff in added_relationship.properties:
        assert before_main_change < prop_diff.changed_at < after_main_change

    # check relationship on removed peer on main
    john_node = nodes_by_id[person_john_main.get_id()]
    assert john_node.uuid == person_john_main.get_id()
    assert john_node.kind == "TestPerson"
    assert john_node.action is DiffAction.UPDATED
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
        DatabaseEdgeType.IS_VISIBLE,
    }
    assert {(p.property_type, p.action, p.previous_value, p.new_value) for p in single_relationship.properties} == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.REMOVED, car_accord_main.id, None),
        (DatabaseEdgeType.IS_VISIBLE, DiffAction.REMOVED, True, None),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.REMOVED, False, None),
    }
    for prop_diff in single_relationship.properties:
        assert before_main_change < prop_diff.changed_at < after_main_change


async def test_relationship_one_property_branch_update(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main,
    person_jane_main,
    person_john_main,
    car_accord_main,
):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    await car_main.owner.update(db=db, data={"id": person_jane_main.id})
    before_main_change = Timestamp()
    await car_main.save(db=db)
    after_main_change = Timestamp()
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await car_branch.owner.update(db=db, data={"id": person_john_main.id, "_relation__is_visible": False})
    before_branch_change = Timestamp()
    await car_branch.save(db=db)
    after_branch_change = Timestamp()

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
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
    property_diff = property_diff_by_type[DatabaseEdgeType.IS_VISIBLE]
    assert property_diff.property_type == DatabaseEdgeType.IS_VISIBLE
    assert property_diff.previous_value is True
    assert property_diff.new_value is False
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
    property_diff = property_diff_by_type[DatabaseEdgeType.IS_VISIBLE]
    assert property_diff.property_type == DatabaseEdgeType.IS_VISIBLE
    assert property_diff.previous_value is True
    assert property_diff.new_value is False
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
    assert len(single_relationship.properties) == 3
    assert before_main_change < single_relationship.changed_at < after_main_change
    property_diff_by_type = {p.property_type: p for p in single_relationship.properties}
    property_diff = property_diff_by_type[DatabaseEdgeType.IS_RELATED]
    assert property_diff.property_type == DatabaseEdgeType.IS_RELATED
    assert property_diff.previous_value is None
    assert property_diff.new_value == person_jane_main.id
    assert property_diff.action is DiffAction.ADDED
    assert before_main_change < property_diff.changed_at < after_main_change
    property_diff = property_diff_by_type[DatabaseEdgeType.IS_VISIBLE]
    assert property_diff.property_type == DatabaseEdgeType.IS_VISIBLE
    assert property_diff.previous_value is None
    assert property_diff.new_value is True
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
    assert len(single_relationship.properties) == 3
    assert before_main_change < single_relationship.changed_at < after_main_change
    property_diff_by_type = {p.property_type: p for p in single_relationship.properties}
    property_diff = property_diff_by_type[DatabaseEdgeType.IS_RELATED]
    assert property_diff.property_type == DatabaseEdgeType.IS_RELATED
    assert property_diff.previous_value == person_john_main.id
    assert property_diff.new_value is None
    assert property_diff.action is DiffAction.REMOVED
    assert before_main_change < property_diff.changed_at < after_main_change
    property_diff = property_diff_by_type[DatabaseEdgeType.IS_VISIBLE]
    assert property_diff.property_type == DatabaseEdgeType.IS_VISIBLE
    assert property_diff.previous_value is True
    assert property_diff.new_value is None
    assert property_diff.action is DiffAction.REMOVED
    assert before_main_change < property_diff.changed_at < after_main_change
    property_diff = property_diff_by_type[DatabaseEdgeType.IS_PROTECTED]
    assert property_diff.property_type == DatabaseEdgeType.IS_PROTECTED
    assert property_diff.previous_value is False
    assert property_diff.new_value is None
    assert property_diff.action is DiffAction.REMOVED
    assert before_main_change < property_diff.changed_at < after_main_change


async def test_add_node_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main,
    person_jane_main,
    person_john_main,
    car_accord_main,
):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    new_car = await Node.init(db=db, branch=branch, schema="TestCar")
    await new_car.new(db=db, name="Batmobile", color="#000000", owner=person_jane_main)
    await new_car.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.nodes == []
    root_path = calculated_diffs.diff_branch_diff
    assert root_path.branch == branch.name
    assert len(root_path.nodes) == 2
    diff_nodes_by_id = {n.uuid: n for n in root_path.nodes}
    node_diff = diff_nodes_by_id[person_jane_main.id]
    assert node_diff.uuid == person_jane_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 0
    assert len(node_diff.relationships) == 1
    relationship_diff = node_diff.relationships[0]
    assert relationship_diff.name == "cars"
    assert relationship_diff.action is DiffAction.UPDATED
    assert len(relationship_diff.relationships) == 1
    single_relationship = relationship_diff.relationships[0]
    assert single_relationship.peer_id == new_car.id
    assert single_relationship.action is DiffAction.ADDED
    assert len(single_relationship.properties) == 3
    assert {p.property_type for p in single_relationship.properties} == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    assert all(p.action is DiffAction.ADDED for p in single_relationship.properties)
    node_diff = diff_nodes_by_id[new_car.id]
    assert node_diff.uuid == new_car.id
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.ADDED
    assert len(node_diff.attributes) == 5
    attributes_by_name = {a.name: a for a in node_diff.attributes}
    assert set(attributes_by_name.keys()) == {"name", "color", "transmission", "nbr_seats", "is_electric"}
    assert all(a.action is DiffAction.ADDED for a in node_diff.attributes)
    attribute_diff = attributes_by_name["name"]
    assert len(attribute_diff.properties) == 3
    assert {(p.property_type, p.action, p.new_value, p.previous_value) for p in attribute_diff.properties} == {
        (DatabaseEdgeType.IS_VISIBLE, DiffAction.ADDED, True, None),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.ADDED, False, None),
        (DatabaseEdgeType.HAS_VALUE, DiffAction.ADDED, "Batmobile", None),
    }
    attribute_diff = attributes_by_name["color"]
    assert len(attribute_diff.properties) == 3
    assert {(p.property_type, p.action, p.new_value, p.previous_value) for p in attribute_diff.properties} == {
        (DatabaseEdgeType.IS_VISIBLE, DiffAction.ADDED, True, None),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.ADDED, False, None),
        (DatabaseEdgeType.HAS_VALUE, DiffAction.ADDED, "#000000", None),
    }
    assert len(node_diff.relationships) == 1
    relationship_diff = node_diff.relationships[0]
    assert relationship_diff.name == "owner"
    assert relationship_diff.action is DiffAction.ADDED
    assert len(relationship_diff.relationships) == 1
    single_relationship = relationship_diff.relationships[0]
    assert single_relationship.peer_id == person_jane_main.id
    assert single_relationship.action is DiffAction.ADDED
    assert len(single_relationship.properties) == 3
    assert {(p.property_type, p.action, p.new_value, p.previous_value) for p in single_relationship.properties} == {
        (DatabaseEdgeType.IS_VISIBLE, DiffAction.ADDED, True, None),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.ADDED, False, None),
        (DatabaseEdgeType.IS_RELATED, DiffAction.ADDED, person_jane_main.id, None),
    }


async def test_many_relationship_property_update(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main,
    person_jane_main,
    car_accord_main,
):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    branch_car = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await branch_car.owner.update(db=db, data={"id": person_john_main.id, "_relation__source": person_jane_main.id})
    await branch_car.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.nodes == []
    root_path = calculated_diffs.diff_branch_diff
    assert root_path.branch == branch.name
    nodes_by_id = {n.uuid: n for n in root_path.nodes}
    assert set(nodes_by_id.keys()) == {person_john_main.get_id(), car_accord_main.get_id()}
    john_node = nodes_by_id[person_john_main.get_id()]
    assert john_node.action is DiffAction.UPDATED
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
    person_john_main,
    person_jane_main,
    person_albert_main,
    car_accord_main,
):
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
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
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
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in [
        (DatabaseEdgeType.IS_RELATED, person_john_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
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
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in [
        (DatabaseEdgeType.IS_RELATED, person_albert_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.previous_value is None
        assert diff_prop.new_value == new_value
        assert from_time < diff_prop.changed_at < branch_update_done
    # check john node on branch
    john_node = nodes_by_id[person_john_main.id]
    assert john_node.action is DiffAction.UPDATED
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
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in [
        (DatabaseEdgeType.IS_RELATED, car_accord_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.previous_value == previous_value
        assert diff_prop.new_value is None
        assert from_time < diff_prop.changed_at < branch_update_done
    # check albert node on branch
    albert_node = nodes_by_id[person_albert_main.id]
    assert albert_node.action is DiffAction.UPDATED
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
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in [
        (DatabaseEdgeType.IS_RELATED, car_accord_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
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
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in [
        (DatabaseEdgeType.IS_RELATED, person_john_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
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
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in [
        (DatabaseEdgeType.IS_RELATED, person_jane_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.previous_value is None
        assert diff_prop.new_value == new_value
        assert branch_update_done < diff_prop.changed_at < main_update_done
    # check john node on main
    john_node = nodes_by_id[person_john_main.id]
    assert john_node.action is DiffAction.UPDATED
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
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in [
        (DatabaseEdgeType.IS_RELATED, car_accord_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.previous_value == previous_value
        assert diff_prop.new_value is None
        assert branch_update_done < diff_prop.changed_at < main_update_done


async def test_relationship_property_owner_conflicting_updates(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main,
    car_accord_main,
):
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
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    # check branch
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 2
    nodes_by_id = {n.uuid: n for n in branch_root_path.nodes}
    assert set(nodes_by_id.keys()) == {person_john_main.get_id(), car_accord_main.get_id()}
    # john node on branch
    john_node = nodes_by_id[person_john_main.get_id()]
    assert john_node.action is DiffAction.UPDATED
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
    car_person_schema_global,
):
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
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.nodes == []
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    diff_node = branch_root_path.nodes.pop()
    assert diff_node.uuid == new_car.get_id()
    assert diff_node.action is DiffAction.UPDATED
    assert diff_node.attributes == []
    assert len(diff_node.relationships) == 1
    diff_relationship = diff_node.relationships.pop()
    assert diff_relationship.name == "owner"
    assert diff_relationship.action is DiffAction.UPDATED
    assert len(diff_relationship.relationships) == 1
    diff_element = diff_relationship.relationships.pop()
    assert diff_element.peer_id == person_1.get_id()
    assert diff_element.action is DiffAction.UPDATED
    diff_props_by_type = {p.property_type: p for p in diff_element.properties}
    assert set(diff_props_by_type.keys()) == {DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.HAS_SOURCE}
    diff_prop_is_related = diff_props_by_type[DatabaseEdgeType.IS_RELATED]
    assert diff_prop_is_related.previous_value == person_1.get_id()
    assert diff_prop_is_related.new_value == person_1.get_id()
    assert diff_prop_is_related.action is DiffAction.UNCHANGED
    diff_prop_has_source = diff_props_by_type[DatabaseEdgeType.HAS_SOURCE]
    assert diff_prop_has_source.previous_value is None
    assert diff_prop_has_source.new_value == person_1.get_id()
    assert diff_prop_has_source.action is DiffAction.ADDED


async def test_agnostic_owner_relationship_added(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_global,
):
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
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.nodes == []
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    diff_nodes_by_id = {n.uuid: n for n in branch_root_path.nodes}
    assert set(diff_nodes_by_id.keys()) == {new_car.get_id(), person_1.get_id()}
    diff_node_car = diff_nodes_by_id[new_car.get_id()]
    assert diff_node_car.action is DiffAction.ADDED
    assert {(attr.name, attr.action) for attr in diff_node_car.attributes} == {
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
        DatabaseEdgeType.IS_VISIBLE,
    }
    diff_prop_tuples = {
        (diff_prop.property_type, diff_prop.action, diff_prop.previous_value, diff_prop.new_value)
        for diff_prop in diff_props_by_type.values()
    }
    assert diff_prop_tuples == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.ADDED, None, person_1.get_id()),
        (DatabaseEdgeType.HAS_OWNER, DiffAction.ADDED, None, person_1.get_id()),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.ADDED, None, False),
        (DatabaseEdgeType.IS_VISIBLE, DiffAction.ADDED, None, True),
    }
    diff_node_person = diff_nodes_by_id[person_1.get_id()]
    assert diff_node_person.action is DiffAction.UPDATED
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
        DatabaseEdgeType.IS_VISIBLE,
    }
    diff_prop_tuples = {
        (diff_prop.property_type, diff_prop.action, diff_prop.previous_value, diff_prop.new_value)
        for diff_prop in diff_props_by_type.values()
    }
    assert diff_prop_tuples == {
        (DatabaseEdgeType.IS_RELATED, DiffAction.ADDED, None, new_car.get_id()),
        (DatabaseEdgeType.HAS_OWNER, DiffAction.ADDED, None, person_1.get_id()),
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.ADDED, None, False),
        (DatabaseEdgeType.IS_VISIBLE, DiffAction.ADDED, None, True),
    }


async def test_update_attribute_under_agnostic_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    fruit_tag_schema_global,
):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    fruit_1 = await Node.init(db=db, schema="GardenFruit", branch=branch)
    await fruit_1.new(db=db, name="blueberry", branch_aware_attr="branchval")
    await fruit_1.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.nodes == []
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    diff_nodes_by_id = {n.uuid: n for n in branch_root_path.nodes}
    assert set(diff_nodes_by_id.keys()) == {fruit_1.get_id()}
    diff_node_fruit = diff_nodes_by_id[fruit_1.get_id()]
    assert diff_node_fruit.action is DiffAction.UPDATED
    assert len(diff_node_fruit.relationships) == 0
    assert len(diff_node_fruit.attributes) == 1
    attr_diff = diff_node_fruit.attributes.pop()
    assert attr_diff.name == "branch_aware_attr"
    assert attr_diff.action is DiffAction.ADDED
    properties_by_type = {p.property_type: p for p in attr_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.HAS_VALUE,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for property_type, new_value in (
        (DatabaseEdgeType.HAS_VALUE, "branchval"),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[property_type]
        assert prop_diff.action is DiffAction.ADDED
        assert prop_diff.previous_value is None
        assert prop_diff.new_value == new_value


async def test_diff_attribute_branch_update_with_previous_base_update_ignored(
    db: InfrahubDatabase, default_branch: Branch, person_alfred_main, person_john_main, car_accord_main
):
    branch = await create_branch(db=db, branch_name="branch")
    # change that will be ignored
    car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    car_main.color.value = "BLURPLE"
    await car_main.save(db=db)
    alfred_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_alfred_main.id)
    alfred_main.name.value = "Big Alfred"
    await alfred_main.save(db=db)
    from_time = Timestamp()
    alfred_branch = await NodeManager.get_one(db=db, branch=branch, id=person_alfred_main.id)
    alfred_branch.name.value = "Little Alfred"
    branch_before_change = Timestamp()
    await alfred_branch.save(db=db)
    branch_after_change = Timestamp()

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        previous_node_specifiers={NodeFieldSpecifier(node_uuid=alfred_main.id, field_name="name")},
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.branch == default_branch.name
    assert len(base_root_path.nodes) == 0
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    node_diff = branch_root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Little Alfred"
    assert property_diff.action is DiffAction.UPDATED
    assert branch_before_change < property_diff.changed_at < branch_after_change


async def test_diff_attribute_branch_update_with_concurrent_base_update_captured(
    db: InfrahubDatabase, default_branch: Branch, person_alfred_main, person_john_main, car_accord_main
):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp()
    # change that will be ignored
    car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    car_main.color.value = "BLURPLE"
    await car_main.save(db=db)
    alfred_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_alfred_main.id)
    alfred_main.name.value = "Big Alfred"
    base_before_change = Timestamp()
    await alfred_main.save(db=db)
    base_after_change = Timestamp()
    alfred_branch = await NodeManager.get_one(db=db, branch=branch, id=person_alfred_main.id)
    alfred_branch.name.value = "Little Alfred"
    branch_before_change = Timestamp()
    await alfred_branch.save(db=db)
    branch_after_change = Timestamp()

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        previous_node_specifiers={NodeFieldSpecifier(node_uuid=alfred_main.id, field_name="name")},
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.branch == default_branch.name
    assert len(base_root_path.nodes) == 1
    node_diff = base_root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Big Alfred"
    assert property_diff.action is DiffAction.UPDATED
    assert base_before_change < property_diff.changed_at < base_after_change
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    node_diff = branch_root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Little Alfred"
    assert property_diff.action is DiffAction.UPDATED
    assert branch_before_change < property_diff.changed_at < branch_after_change


async def test_diff_attribute_branch_update_with_previous_base_update_captured(
    db: InfrahubDatabase, default_branch: Branch, person_alfred_main, person_john_main, car_accord_main
):
    branch = await create_branch(db=db, branch_name="branch")
    # change that will be ignored
    car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    car_main.color.value = "BLURPLE"
    await car_main.save(db=db)
    alfred_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_alfred_main.id)
    alfred_main.name.value = "Big Alfred"
    base_before_change = Timestamp()
    await alfred_main.save(db=db)
    base_after_change = Timestamp()
    from_time = Timestamp()
    alfred_branch = await NodeManager.get_one(db=db, branch=branch, id=person_alfred_main.id)
    alfred_branch.name.value = "Little Alfred"
    branch_before_change = Timestamp()
    await alfred_branch.save(db=db)
    branch_after_change = Timestamp()

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.branch == default_branch.name
    assert len(base_root_path.nodes) == 1
    node_diff = base_root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Big Alfred"
    assert property_diff.action is DiffAction.UPDATED
    assert base_before_change < property_diff.changed_at < base_after_change
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    node_diff = branch_root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Little Alfred"
    assert property_diff.action is DiffAction.UPDATED
    assert branch_before_change < property_diff.changed_at < branch_after_change


async def test_diff_attribute_branch_update_with_separate_previous_base_update_captured(
    db: InfrahubDatabase, default_branch: Branch, person_alfred_main, person_john_main, car_accord_main
):
    branch = await create_branch(db=db, branch_name="branch")
    alfred_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_alfred_main.id)
    alfred_main.name.value = "Big Alfred"
    await alfred_main.save(db=db)
    from_time = Timestamp()
    car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    car_main.color.value = "BLURPLE"
    base_before_change = Timestamp()
    await car_main.save(db=db)
    base_after_change = Timestamp()
    alfred_branch = await NodeManager.get_one(db=db, branch=branch, id=person_alfred_main.id)
    alfred_branch.name.value = "Little Alfred"
    branch_before_change = Timestamp()
    await alfred_branch.save(db=db)
    branch_after_change = Timestamp()

    diff_calculator = DiffCalculator(db=db)

    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        previous_node_specifiers={
            NodeFieldSpecifier(node_uuid=car_accord_main.id, field_name="color"),
            NodeFieldSpecifier(node_uuid=person_alfred_main.id, field_name="name"),
        },
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.branch == default_branch.name
    assert len(base_root_path.nodes) == 1
    nodes_by_id = {n.uuid: n for n in base_root_path.nodes}
    node_diff = nodes_by_id[car_accord_main.id]
    assert node_diff.uuid == car_accord_main.id
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "color"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == "#444444"
    assert property_diff.new_value == "BLURPLE"
    assert property_diff.action is DiffAction.UPDATED
    assert base_before_change < property_diff.changed_at < base_after_change
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    node_diff = branch_root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Little Alfred"
    assert property_diff.action is DiffAction.UPDATED
    assert branch_before_change < property_diff.changed_at < branch_after_change


async def test_branch_node_delete_with_base_updates(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main, person_john_main, person_jane_main
):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp()
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await car_branch.delete(db=db)

    car_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
    car_main.color.value = "blurple"
    await car_main.owner.update(db=db, data={"id": person_jane_main.id})
    await car_main.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.branch == default_branch.name
    node_diffs_by_id = {n.uuid: n for n in base_root_path.nodes}
    assert set(node_diffs_by_id.keys()) == {car_accord_main.id, person_john_main.id}
    node_diff = node_diffs_by_id[car_accord_main.id]
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.relationships) == 1
    rel_diffs_by_name = {r.name: r for r in node_diff.relationships}
    rel_diff = rel_diffs_by_name["owner"]
    assert rel_diff.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in rel_diff.relationships}
    assert set(elements_by_peer_id.keys()) == {person_john_main.id, person_jane_main.id}
    added_element = elements_by_peer_id[person_jane_main.id]
    assert added_element.action is DiffAction.ADDED
    properties_by_type = {p.property_type: p for p in added_element.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_PROTECTED,
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_PROTECTED, False),
        (DatabaseEdgeType.IS_RELATED, person_jane_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
    ):
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.action is DiffAction.ADDED
        assert diff_prop.previous_value is None
        assert diff_prop.new_value == new_value
    removed_element = elements_by_peer_id[person_john_main.id]
    assert removed_element.action is DiffAction.REMOVED
    properties_by_type = {p.property_type: p for p in removed_element.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_PROTECTED,
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_PROTECTED, False),
        (DatabaseEdgeType.IS_RELATED, person_john_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
    ):
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.action is DiffAction.REMOVED
        assert diff_prop.previous_value == previous_value
        assert diff_prop.new_value is None
    peer_node_diff = node_diffs_by_id[person_john_main.id]
    assert peer_node_diff.action is DiffAction.UPDATED
    assert len(peer_node_diff.attributes) == 0
    assert len(peer_node_diff.relationships) == 1
    rel_diffs_by_name = {r.name: r for r in peer_node_diff.relationships}
    rel_diff = rel_diffs_by_name["cars"]
    assert rel_diff.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in rel_diff.relationships}
    assert len(elements_by_peer_id) == 1
    removed_element = elements_by_peer_id[car_accord_main.id]
    assert removed_element.action is DiffAction.REMOVED
    properties_by_type = {p.property_type: p for p in removed_element.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_PROTECTED,
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_PROTECTED, False),
        (DatabaseEdgeType.IS_RELATED, car_accord_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
    ):
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.action is DiffAction.REMOVED
        assert diff_prop.previous_value == previous_value
        assert diff_prop.new_value is None
    attributes_by_name = {attr.name: attr for attr in node_diff.attributes}
    assert len(attributes_by_name) == 1
    attribute_diff = attributes_by_name["color"]
    assert attribute_diff.action is DiffAction.UPDATED
    properties_by_type = {prop.property_type: prop for prop in attribute_diff.properties}
    assert len(properties_by_type) == 1
    diff_property = properties_by_type[DatabaseEdgeType.HAS_VALUE]
    assert diff_property.action is DiffAction.UPDATED
    assert diff_property.previous_value == "#444444"
    assert diff_property.new_value == "blurple"

    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 2
    node_diffs_by_id = {n.uuid: n for n in branch_root_path.nodes}
    assert set(node_diffs_by_id.keys()) == {car_accord_main.id, person_john_main.id}
    node_diff = node_diffs_by_id[car_accord_main.id]
    assert node_diff.uuid == car_accord_main.id
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.REMOVED
    assert len(node_diff.attributes) == 5
    assert len(node_diff.relationships) == 1
    relationship_diff = node_diff.relationships[0]
    attributes_by_name = {attr.name: attr for attr in node_diff.attributes}
    assert set(attributes_by_name.keys()) == {"name", "nbr_seats", "color", "is_electric", "transmission"}
    for attribute_diff in attributes_by_name.values():
        assert attribute_diff.action is DiffAction.REMOVED
        properties_by_type = {prop.property_type: prop for prop in attribute_diff.properties}
        diff_property = properties_by_type[DatabaseEdgeType.HAS_VALUE]
        assert diff_property.action is DiffAction.REMOVED
        assert diff_property.new_value in (None, "NULL")
    assert len(node_diff.relationships) == 1
    relationship_diff = node_diff.relationships[0]
    assert relationship_diff.name == "owner"
    assert relationship_diff.action is DiffAction.REMOVED
    assert len(relationship_diff.relationships) == 1
    single_relationship_diff = relationship_diff.relationships[0]
    assert single_relationship_diff.peer_id == person_john_main.id
    assert single_relationship_diff.action is DiffAction.REMOVED
    node_diff = node_diffs_by_id[person_john_main.id]
    assert node_diff.uuid == person_john_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 0
    assert len(node_diff.relationships) == 1
    relationship_diff = node_diff.relationships[0]
    assert relationship_diff.name == "cars"
    assert relationship_diff.action is DiffAction.UPDATED
    assert len(relationship_diff.relationships) == 1
    single_relationship_diff = relationship_diff.relationships[0]
    assert single_relationship_diff.peer_id == car_branch.id
    assert single_relationship_diff.action is DiffAction.REMOVED
    assert len(single_relationship_diff.properties) == 3
    for diff_property in single_relationship_diff.properties:
        assert diff_property.action is DiffAction.REMOVED


async def test_branch_relationship_delete_with_property_update(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
):
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")
    persons = []
    for i in range(3):
        person = await Node.init(db=db, schema=person_schema, branch=default_branch)
        await person.new(db=db, name=f"Person{i}")
        await person.save(db=db)
        persons.append(person)
    dogs = []
    for i in range(3):
        dog = await Node.init(db=db, schema=dog_schema, branch=default_branch)
        await dog.new(db=db, name=f"Dog{i}", breed=f"Breed{i}", owner=persons[i], best_friend=persons[i])
        await dog.save(db=db)
        dogs.append(dog)
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp()
    dog_branch = await NodeManager.get_one(db=db, branch=branch, id=dogs[0].id)
    before_branch_change = Timestamp()
    await dog_branch.best_friend.update(db=db, data=[None])
    await dog_branch.save(db=db)
    after_branch_change = Timestamp()

    dog_main = await NodeManager.get_one(db=db, id=dogs[0].id)
    before_main_change = Timestamp()
    await dog_main.best_friend.update(db=db, data={"id": persons[0].id, "_relation__is_visible": False})
    await dog_main.save(db=db)
    after_main_change = Timestamp()

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    base_diff = calculated_diffs.base_branch_diff
    assert base_diff.branch == default_branch.name
    node_diffs_by_id = {n.uuid: n for n in base_diff.nodes}
    node_diff = node_diffs_by_id[dog_main.id]
    assert node_diff.uuid == dog_main.id
    assert node_diff.kind == "TestDog"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 0
    assert len(node_diff.relationships) == 1
    rel_diffs_by_name = {r.name: r for r in node_diff.relationships}
    rel_diff = rel_diffs_by_name["best_friend"]
    assert rel_diff.cardinality is RelationshipCardinality.ONE
    assert rel_diff.action is DiffAction.UPDATED
    assert len(rel_diff.relationships) == 1
    rel_elements_by_peer_id = {e.peer_id: e for e in rel_diff.relationships}
    rel_element_diff = rel_elements_by_peer_id[persons[0].id]
    assert rel_element_diff.action is DiffAction.UPDATED
    prop_diff_by_type = {p.property_type: p for p in rel_element_diff.properties}
    assert set(prop_diff_by_type.keys()) == {DatabaseEdgeType.IS_RELATED, DatabaseEdgeType.IS_VISIBLE}
    visible_prop = prop_diff_by_type[DatabaseEdgeType.IS_VISIBLE]
    assert visible_prop.action is DiffAction.UPDATED
    assert visible_prop.new_value is False
    assert visible_prop.previous_value is True
    assert before_main_change < visible_prop.changed_at < after_main_change
    related_prop = prop_diff_by_type[DatabaseEdgeType.IS_RELATED]
    assert related_prop.action is DiffAction.UNCHANGED
    assert related_prop.new_value == persons[0].id
    assert related_prop.previous_value == persons[0].id
    assert related_prop.changed_at < from_time

    branch_diff = calculated_diffs.diff_branch_diff
    assert branch_diff.branch == branch.name
    node_diffs_by_id = {n.uuid: n for n in branch_diff.nodes}
    assert set(node_diffs_by_id.keys()) == {dog_branch.id, persons[0].id}
    dog_node = node_diffs_by_id[dog_branch.id]
    assert dog_node.action is DiffAction.UPDATED
    assert len(dog_node.attributes) == 0
    assert len(dog_node.relationships) == 1
    rel_diffs_by_name = {r.name: r for r in dog_node.relationships}
    rel_diff = rel_diffs_by_name["best_friend"]
    assert rel_diff.cardinality is RelationshipCardinality.ONE
    assert rel_diff.action is DiffAction.REMOVED
    assert len(rel_diff.relationships) == 1
    rel_elements_by_peer_id = {e.peer_id: e for e in rel_diff.relationships}
    rel_element_diff = rel_elements_by_peer_id[persons[0].id]
    assert rel_element_diff.action is DiffAction.REMOVED
    prop_diff_by_type = {p.property_type: p for p in rel_element_diff.properties}
    assert len(prop_diff_by_type) == 3
    for property_type, previous_value in [
        (DatabaseEdgeType.IS_RELATED, persons[0].id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        prop_diff = prop_diff_by_type[property_type]
        assert prop_diff.action is DiffAction.REMOVED
        assert prop_diff.new_value is None
        assert prop_diff.previous_value == previous_value
        assert before_branch_change < prop_diff.changed_at < after_branch_change
    person_node = node_diffs_by_id[persons[0].id]
    assert person_node.action is DiffAction.UPDATED
    assert len(person_node.attributes) == 0
    assert len(person_node.relationships) == 1
    rel_diffs_by_name = {r.name: r for r in person_node.relationships}
    rel_diff = rel_diffs_by_name["best_friends"]
    assert rel_diff.cardinality is RelationshipCardinality.MANY
    assert rel_diff.action is DiffAction.UPDATED
    assert len(rel_diff.relationships) == 1
    rel_elements_by_peer_id = {e.peer_id: e for e in rel_diff.relationships}
    rel_element_diff = rel_elements_by_peer_id[dog_branch.id]
    assert rel_element_diff.action is DiffAction.REMOVED
    prop_diff_by_type = {p.property_type: p for p in rel_element_diff.properties}
    assert len(prop_diff_by_type) == 3
    for property_type, previous_value in [
        (DatabaseEdgeType.IS_RELATED, dog_branch.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        prop_diff = prop_diff_by_type[property_type]
        assert prop_diff.action is DiffAction.REMOVED
        assert prop_diff.new_value is None
        assert prop_diff.previous_value == previous_value
        assert before_branch_change < prop_diff.changed_at < after_branch_change


async def test_node_deleted_on_both(
    db: InfrahubDatabase, default_branch: Branch, person_alfred_main, person_john_main, car_accord_main
):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    alfred_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_alfred_main.id)
    await alfred_main.delete(db=db)
    alfred_branch = await NodeManager.get_one(db=db, branch=branch, id=person_alfred_main.id)
    await alfred_branch.delete(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    for diff_root in (calculated_diffs.base_branch_diff, calculated_diffs.diff_branch_diff):
        assert len(diff_root.nodes) == 1
        diff_node = diff_root.nodes.pop()
        assert diff_node.action is DiffAction.REMOVED
        assert diff_node.uuid == person_alfred_main.id
        attributes_by_name = {a.name: a for a in diff_node.attributes}
        assert set(attributes_by_name.keys()) == {"name", "height"}
        for attr_diff in diff_node.attributes:
            assert attr_diff.action is DiffAction.REMOVED
            props_by_type = {p.property_type: p for p in attr_diff.properties}
            assert set(props_by_type.keys()) == {
                DatabaseEdgeType.HAS_VALUE,
                DatabaseEdgeType.IS_PROTECTED,
                DatabaseEdgeType.IS_VISIBLE,
            }
            for prop_diff in attr_diff.properties:
                assert prop_diff.action is DiffAction.REMOVED
        assert len(diff_node.relationships) == 0


async def test_relationship_updated_then_node_deleted(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main,
    person_john_main,
    person_jane_main,
    car_accord_main,
    car_camry_main,
):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_camry_main.id)
    await car_main.owner.update(db=db, data={"id": person_alfred_main.id})
    await car_main.save(db=db)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    await car_branch.owner.update(db=db, data={"id": person_alfred_main.id})
    await car_branch.save(db=db)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    await car_branch.delete(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    branch_diff_root = calculated_diffs.diff_branch_diff
    nodes_by_id = {n.uuid: n for n in branch_diff_root.nodes}
    assert set(nodes_by_id.keys()) == {car_camry_main.id, person_jane_main.id}
    car_base_diff = nodes_by_id[car_camry_main.id]
    assert car_base_diff.action is DiffAction.REMOVED
    attributes_by_name = {a.name: a for a in car_base_diff.attributes}
    assert set(attributes_by_name.keys()) == {"color", "nbr_seats", "transmission", "is_electric", "name"}
    for attr_diff in attributes_by_name.values():
        assert attr_diff.action is DiffAction.REMOVED
        properties_by_type = {p.property_type: p for p in attr_diff.properties}
        assert set(properties_by_type.keys()) == {
            DatabaseEdgeType.HAS_VALUE,
            DatabaseEdgeType.IS_VISIBLE,
            DatabaseEdgeType.IS_PROTECTED,
        }
        for prop_type, previous_value in (
            (DatabaseEdgeType.HAS_VALUE, getattr(car_main, attr_diff.name).value),
            (DatabaseEdgeType.IS_VISIBLE, True),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ):
            prop_diff = properties_by_type[prop_type]
            assert prop_diff.action is DiffAction.REMOVED
            assert prop_diff.previous_value in (
                (previous_value, "NULL") if previous_value is None else (previous_value,)
            )
            assert prop_diff.new_value in (None, "NULL")
    relationships_by_name = {r.name: r for r in car_base_diff.relationships}
    assert set(relationships_by_name.keys()) == {"owner"}
    relationship_diff = relationships_by_name["owner"]
    assert relationship_diff.action is DiffAction.REMOVED
    assert len(relationship_diff.relationships) == 1
    removed_element_diff = relationship_diff.relationships.pop()
    assert removed_element_diff.peer_id == person_jane_main.id
    assert removed_element_diff.action is DiffAction.REMOVED
    properties_by_type = {p.property_type: p for p in removed_element_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_RELATED, person_jane_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[prop_type]
        assert prop_diff.action is DiffAction.REMOVED
        assert prop_diff.previous_value == previous_value
        assert prop_diff.new_value in (None, "NULL")
    person_base_diff = nodes_by_id[person_jane_main.id]
    assert person_base_diff.action is DiffAction.UPDATED
    assert len(person_base_diff.attributes) == 0
    relationships_by_name = {r.name: r for r in person_base_diff.relationships}
    assert set(relationships_by_name.keys()) == {"cars"}
    rel_diff = relationships_by_name["cars"]
    assert rel_diff.action is DiffAction.UPDATED
    assert len(rel_diff.relationships) == 1
    removed_element_diff = rel_diff.relationships.pop()
    assert removed_element_diff.peer_id == car_camry_main.id
    assert removed_element_diff.action is DiffAction.REMOVED
    properties_by_type = {p.property_type: p for p in removed_element_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[prop_type]
        assert prop_diff.action is DiffAction.REMOVED
        assert prop_diff.previous_value == previous_value
        assert prop_diff.new_value in (None, "NULL")

    base_diff_root = calculated_diffs.base_branch_diff
    nodes_by_id = {n.uuid: n for n in base_diff_root.nodes}
    assert set(nodes_by_id.keys()) == {car_camry_main.id, person_jane_main.id}
    car_base_diff = nodes_by_id[car_camry_main.id]
    assert car_base_diff.action is DiffAction.UPDATED
    assert len(car_base_diff.attributes) == 0
    relationships_by_name = {r.name: r for r in car_base_diff.relationships}
    assert set(relationships_by_name.keys()) == {"owner"}
    relationship_diff = relationships_by_name["owner"]
    assert relationship_diff.action is DiffAction.UPDATED
    assert len(relationship_diff.relationships) == 2
    elements_by_peer_id = {e.peer_id: e for e in relationship_diff.relationships}
    removed_element_diff = elements_by_peer_id[person_jane_main.id]
    assert removed_element_diff.action is DiffAction.REMOVED
    properties_by_type = {p.property_type: p for p in removed_element_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_RELATED, person_jane_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[prop_type]
        assert prop_diff.action is DiffAction.REMOVED
        assert prop_diff.previous_value == previous_value
        assert prop_diff.new_value in (None, "NULL")
    added_element_diff = elements_by_peer_id[person_alfred_main.id]
    assert added_element_diff.action is DiffAction.ADDED
    properties_by_type = {p.property_type: p for p in added_element_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_RELATED, person_alfred_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[prop_type]
        assert prop_diff.action is DiffAction.ADDED
        assert prop_diff.previous_value in (None, "NULL")
        assert prop_diff.new_value == new_value

    person_base_diff = nodes_by_id[person_jane_main.id]
    assert person_base_diff.action is DiffAction.UPDATED
    assert len(person_base_diff.attributes) == 0
    relationships_by_name = {r.name: r for r in person_base_diff.relationships}
    assert set(relationships_by_name.keys()) == {"cars"}
    rel_diff = relationships_by_name["cars"]
    assert rel_diff.action is DiffAction.UPDATED
    assert len(rel_diff.relationships) == 1
    removed_element_diff = rel_diff.relationships.pop()
    assert removed_element_diff.peer_id == car_camry_main.id
    assert removed_element_diff.action is DiffAction.REMOVED
    properties_by_type = {p.property_type: p for p in removed_element_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[prop_type]
        assert prop_diff.action is DiffAction.REMOVED
        assert prop_diff.previous_value == previous_value
        assert prop_diff.new_value in (None, "NULL")


async def test_node_added_and_deleted_on_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main,
    person_john_main,
    person_jane_main,
    car_accord_main,
    car_camry_main,
):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    new_car = await Node.init(schema="TestCar", db=db, branch=branch)
    await new_car.new(db=db, name="newcar", color="blue", owner=person_jane_main)
    await new_car.save(db=db)
    retrieved_car = await NodeManager.get_one(db=db, branch=branch, id=new_car.id)
    await retrieved_car.delete(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    branch_diff_root = calculated_diffs.diff_branch_diff
    assert branch_diff_root.nodes == []
    base_diff_root = calculated_diffs.base_branch_diff
    assert base_diff_root.nodes == []


async def test_property_update_then_relationship_deleted(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main,
    person_john_main,
    person_jane_main,
    car_accord_main,
    car_camry_main,
):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    await car_branch.owner.update(db=db, data={"id": person_jane_main.id, "_relation__owner": person_alfred_main.id})
    await car_branch.save(db=db)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    await car_branch.owner.update(db=db, data={"id": person_john_main.id})
    await car_branch.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    branch_diff_root = calculated_diffs.diff_branch_diff
    nodes_by_id = {n.uuid: n for n in branch_diff_root.nodes}
    assert set(nodes_by_id.keys()) == {person_jane_main.id, person_john_main.id, car_camry_main.id}
    car_branch_diff = nodes_by_id[car_camry_main.id]
    assert car_branch_diff.action is DiffAction.UPDATED
    assert len(car_branch_diff.attributes) == 0
    relationships_by_name = {r.name: r for r in car_branch_diff.relationships}
    assert set(relationships_by_name.keys()) == {"owner"}
    rel_diff = relationships_by_name["owner"]
    assert rel_diff.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in rel_diff.relationships}
    removed_element_diff = elements_by_peer_id[person_jane_main.id]
    assert removed_element_diff.action is DiffAction.REMOVED
    properties_by_type = {p.property_type: p for p in removed_element_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_RELATED, person_jane_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[prop_type]
        assert prop_diff.action is DiffAction.REMOVED
        assert prop_diff.previous_value == previous_value
        assert prop_diff.new_value in (None, "NULL")
    added_element_diff = elements_by_peer_id[person_john_main.id]
    assert added_element_diff.action is DiffAction.ADDED
    properties_by_type = {p.property_type: p for p in added_element_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_RELATED, person_john_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[prop_type]
        assert prop_diff.action is DiffAction.ADDED
        assert prop_diff.previous_value in (None, "NULL")
        assert prop_diff.new_value == new_value

    person_removed_branch_diff = nodes_by_id[person_jane_main.id]
    assert person_removed_branch_diff.action is DiffAction.UPDATED
    assert len(person_removed_branch_diff.attributes) == 0
    relationships_by_name = {r.name: r for r in person_removed_branch_diff.relationships}
    assert set(relationships_by_name.keys()) == {"cars"}
    rel_diff = relationships_by_name["cars"]
    assert rel_diff.action is DiffAction.UPDATED
    assert len(rel_diff.relationships) == 1
    removed_element_diff = rel_diff.relationships.pop()
    assert removed_element_diff.peer_id == car_camry_main.id
    assert removed_element_diff.action is DiffAction.REMOVED
    properties_by_type = {p.property_type: p for p in removed_element_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[prop_type]
        assert prop_diff.action is DiffAction.REMOVED
        assert prop_diff.previous_value == previous_value
        assert prop_diff.new_value in (None, "NULL")

    person_added_branch_diff = nodes_by_id[person_john_main.id]
    assert person_added_branch_diff.action is DiffAction.UPDATED
    assert len(person_added_branch_diff.attributes) == 0
    relationships_by_name = {r.name: r for r in person_added_branch_diff.relationships}
    assert set(relationships_by_name.keys()) == {"cars"}
    rel_diff = relationships_by_name["cars"]
    assert rel_diff.action is DiffAction.UPDATED
    assert len(rel_diff.relationships) == 1
    removed_element_diff = rel_diff.relationships.pop()
    assert removed_element_diff.peer_id == car_camry_main.id
    assert removed_element_diff.action is DiffAction.ADDED
    properties_by_type = {p.property_type: p for p in removed_element_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[prop_type]
        assert prop_diff.action is DiffAction.ADDED
        assert prop_diff.previous_value in (None, "NULL")
        assert prop_diff.new_value == new_value

    base_diff_root = calculated_diffs.base_branch_diff
    assert base_diff_root.nodes == []
