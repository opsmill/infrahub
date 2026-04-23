import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.calculator import DiffCalculator
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


@pytest.mark.parametrize("use_branch", [True, False])
async def test_node_delete(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, person_john_main: Node, use_branch: bool
) -> None:
    if use_branch:
        branch = await create_branch(db=db, branch_name="branch")
    else:
        branch = default_branch
    from_time = Timestamp()
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await car_branch.delete(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
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
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 7
    assert len(node_diff.relationships) == 1
    relationship_diff = node_diff.relationships[0]
    attributes_by_name = {attr.name: attr for attr in node_diff.attributes}
    assert set(attributes_by_name.keys()) == {
        "name",
        "nbr_seats",
        "color",
        "display_label",
        "is_electric",
        "transmission",
        "human_friendly_id",
    }
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
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 0
    assert len(node_diff.relationships) == 1
    relationship_diff = node_diff.relationships[0]
    assert relationship_diff.name == "cars"
    assert relationship_diff.action is DiffAction.UPDATED
    assert len(relationship_diff.relationships) == 1
    single_relationship_diff = relationship_diff.relationships[0]
    assert single_relationship_diff.peer_id == car_branch.id
    assert single_relationship_diff.action is DiffAction.REMOVED
    assert len(single_relationship_diff.properties) == 2
    for diff_property in single_relationship_diff.properties:
        assert diff_property.action is DiffAction.REMOVED


async def test_node_base_delete_branch_update(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, person_john_main: Node
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp()
    car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    await car_main.delete(db=db)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    car_branch.nbr_seats.value = 10
    await car_branch.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert len(base_root_path.nodes) == 1
    node_diffs_by_id = {n.uuid: n for n in base_root_path.nodes}
    node_diff = node_diffs_by_id[car_accord_main.id]
    assert node_diff.uuid == car_accord_main.id
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.REMOVED
    assert node_diff.is_node_kind_migration is False
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    node_diffs_by_id = {n.uuid: n for n in branch_root_path.nodes}
    node_diff = node_diffs_by_id[car_accord_main.id]
    assert node_diff.uuid == car_accord_main.id
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
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


async def test_node_branch_add(db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    new_person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await new_person.new(db=db, name="Stokely")
    before_change = Timestamp()
    await new_person.save(db=db)
    after_change = Timestamp()

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
    assert len(branch_root_path.nodes) == 1
    node_diff = branch_root_path.nodes[0]
    assert node_diff.uuid == new_person.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.ADDED
    assert node_diff.is_node_kind_migration is False
    assert before_change < node_diff.changed_at < after_change
    attributes_by_name = {attr.name: attr for attr in node_diff.attributes}
    assert set(attributes_by_name.keys()) == {"name", "height", "human_friendly_id", "display_label"}
    attribute_diff = attributes_by_name["name"]
    assert attribute_diff.action is DiffAction.ADDED
    assert before_change < attribute_diff.changed_at < after_change
    properties_by_type = {prop.property_type: prop for prop in attribute_diff.properties}
    diff_property = properties_by_type[DatabaseEdgeType.HAS_VALUE]
    assert diff_property.action is DiffAction.ADDED
    assert diff_property.new_value == "Stokely"
    assert before_change < diff_property.changed_at < after_change


async def test_add_node_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_jane_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    new_car = await Node.init(db=db, branch=branch, schema="TestCar")
    await new_car.new(db=db, name="Batmobile", color="#000000", owner=person_alfred_main)
    await new_car.save(db=db)
    fresh_new_car = await NodeManager.get_one(db=db, branch=branch, id=new_car.id)
    await fresh_new_car.owner.update(db=db, data=person_jane_main)
    await fresh_new_car.save(db=db)

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
    assert len(root_path.nodes) == 2
    diff_nodes_by_id = {n.uuid: n for n in root_path.nodes}
    node_diff = diff_nodes_by_id[person_jane_main.id]
    assert node_diff.uuid == person_jane_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 0
    assert len(node_diff.relationships) == 1
    relationship_diff = node_diff.relationships[0]
    assert relationship_diff.name == "cars"
    assert relationship_diff.action is DiffAction.UPDATED
    assert len(relationship_diff.relationships) == 1
    single_relationship = relationship_diff.relationships[0]
    assert single_relationship.peer_id == new_car.id
    assert single_relationship.action is DiffAction.ADDED
    assert len(single_relationship.properties) == 2
    assert {p.property_type for p in single_relationship.properties} == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    assert all(p.action is DiffAction.ADDED for p in single_relationship.properties)
    node_diff = diff_nodes_by_id[new_car.id]
    assert node_diff.uuid == new_car.id
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.ADDED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 7
    attributes_by_name = {a.name: a for a in node_diff.attributes}
    assert set(attributes_by_name.keys()) == {
        "name",
        "color",
        "display_label",
        "transmission",
        "nbr_seats",
        "is_electric",
        "human_friendly_id",
    }
    assert all(a.action is DiffAction.ADDED for a in node_diff.attributes)
    attribute_diff = attributes_by_name["name"]
    assert len(attribute_diff.properties) == 2
    assert {(p.property_type, p.action, p.new_value, p.previous_value) for p in attribute_diff.properties} == {
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.ADDED, False, None),
        (DatabaseEdgeType.HAS_VALUE, DiffAction.ADDED, "Batmobile", None),
    }
    attribute_diff = attributes_by_name["color"]
    assert len(attribute_diff.properties) == 2
    assert {(p.property_type, p.action, p.new_value, p.previous_value) for p in attribute_diff.properties} == {
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
    assert len(single_relationship.properties) == 2
    assert {(p.property_type, p.action, p.new_value, p.previous_value) for p in single_relationship.properties} == {
        (DatabaseEdgeType.IS_PROTECTED, DiffAction.ADDED, False, None),
        (DatabaseEdgeType.IS_RELATED, DiffAction.ADDED, person_jane_main.id, None),
    }


async def test_node_deleted_on_both(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    alfred_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_alfred_main.id)
    await alfred_main.delete(db=db)
    alfred_branch = await NodeManager.get_one(db=db, branch=branch, id=person_alfred_main.id)
    await alfred_branch.delete(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    for diff_root in (calculated_diffs.base_branch_diff, calculated_diffs.diff_branch_diff):
        assert len(diff_root.nodes) == 1
        diff_node = diff_root.nodes.pop()
        assert diff_node.action is DiffAction.REMOVED
        assert diff_node.uuid == person_alfred_main.id
        assert diff_node.is_node_kind_migration is False
        attributes_by_name = {a.name: a for a in diff_node.attributes}
        assert set(attributes_by_name.keys()) == {"name", "height", "human_friendly_id", "display_label"}
        for attr_diff in diff_node.attributes:
            assert attr_diff.action is DiffAction.REMOVED
            props_by_type = {p.property_type: p for p in attr_diff.properties}
            assert set(props_by_type.keys()) == {
                DatabaseEdgeType.HAS_VALUE,
                DatabaseEdgeType.IS_PROTECTED,
            }
            for prop_diff in attr_diff.properties:
                assert prop_diff.action is DiffAction.REMOVED
        assert len(diff_node.relationships) == 0


async def test_node_added_and_deleted_on_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_john_main: Node,
    person_jane_main: Node,
    car_accord_main: Node,
    car_camry_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    new_car = await Node.init(schema="TestCar", db=db, branch=branch)
    await new_car.new(db=db, name="newcar", color="blue", owner=person_jane_main)
    await new_car.save(db=db)
    retrieved_car = await NodeManager.get_one(db=db, branch=branch, id=new_car.id)
    await retrieved_car.delete(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    branch_diff_root = calculated_diffs.diff_branch_diff
    assert branch_diff_root.nodes == []
    base_diff_root = calculated_diffs.base_branch_diff
    assert base_diff_root.nodes == []


async def test_create_local_and_aware_nodes_on_branch(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_branch_local: SchemaBranch
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp()
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name="Guy", height=180)
    await person.save(db=db)
    # car is a local node
    car = await Node.init(db=db, schema="TestCar", branch=branch)
    await car.new(db=db, name="camry", owner=person.id)
    await car.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    base_branch_diff = calculated_diffs.base_branch_diff
    assert len(base_branch_diff.nodes) == 0

    diff_branch_diff = calculated_diffs.diff_branch_diff
    nodes_by_id = {n.uuid: n for n in diff_branch_diff.nodes}
    assert set(nodes_by_id.keys()) == {person.id}
    node_diff = nodes_by_id[person.id]
    assert node_diff.action is DiffAction.ADDED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.relationships) == 0
    attrs_by_name = {a.name: a for a in node_diff.attributes}
    assert set(attrs_by_name.keys()) == {"name", "height", "human_friendly_id", "display_label"}
    for attr_diff in node_diff.attributes:
        assert attr_diff.action is DiffAction.ADDED


async def test_create_aware_and_agnostic_nodes_on_branch(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_global: None
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp()
    # person is an agnostic node
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name="Guy", height=180)
    await person.save(db=db)
    # nbr_seats is an agnostic attr
    car = await Node.init(db=db, schema="TestCar", branch=branch)
    await car.new(db=db, name="camry", nbr_seats=3, is_electric=True, owner=person.id)
    await car.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch, diff_branch=branch, from_time=from_time, to_time=Timestamp()
    )

    base_branch_diff = calculated_diffs.base_branch_diff
    assert len(base_branch_diff.nodes) == 0

    diff_branch_diff = calculated_diffs.diff_branch_diff
    nodes_by_id = {n.uuid: n for n in diff_branch_diff.nodes}
    assert set(nodes_by_id.keys()) == {car.id, person.id}
    # check car attributes and relationship
    node_diff = nodes_by_id[car.id]
    assert node_diff.action is DiffAction.ADDED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.relationships) == 1
    rel_diff = node_diff.relationships.pop()
    assert rel_diff.name == "owner"
    assert rel_diff.action is DiffAction.ADDED
    attrs_by_name = {a.name: a for a in node_diff.attributes}
    # nbr_seats is agnostic, so is not included
    assert set(attrs_by_name.keys()) == {"name", "color", "is_electric", "human_friendly_id", "display_label"}
    for attr_diff in node_diff.attributes:
        assert attr_diff.action is DiffAction.ADDED
    # check person relationship
    node_diff = nodes_by_id[person.id]
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 0
    assert len(node_diff.relationships) == 1
    rel_diff = node_diff.relationships.pop()
    assert rel_diff.name == "cars"
    assert rel_diff.action is DiffAction.UPDATED
