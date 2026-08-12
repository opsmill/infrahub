import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.calculator import DiffCalculator
from infrahub.core.diff.model.path import DiffRoot
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


async def test_diff_attribute_branch_update(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
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
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    main_root_path = calculated_diffs.base_branch_diff
    assert main_root_path.branch == default_branch.name
    assert len(main_root_path.nodes) == 1
    node_diff = main_root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 3
    node_diff.attributes.sort(key=lambda da: da.name, reverse=True)
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
    attribute_diff = node_diff.attributes[1]
    assert attribute_diff.name == "human_friendly_id"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == '["Alfred"]'
    assert property_diff.new_value == '["Big Alfred"]'
    assert property_diff.action is DiffAction.UPDATED
    assert main_before_change < property_diff.changed_at < main_after_change
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    node_diff = branch_root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 3
    node_diff.attributes.sort(key=lambda da: da.name, reverse=True)
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
    attribute_diff = node_diff.attributes[1]
    assert attribute_diff.name == "human_friendly_id"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == '["Alfred"]'
    assert property_diff.new_value == '["Little Alfred"]'
    assert property_diff.action is DiffAction.UPDATED
    assert branch_before_change < property_diff.changed_at < branch_after_change


async def test_attribute_property_main_update(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
    from_time = Timestamp()
    alfred_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_alfred_main.id)
    alfred_main.name.is_protected = True
    before_change = Timestamp()
    await alfred_main.save(db=db)
    after_change = Timestamp()

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=default_branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
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
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    properties_by_type = {p.property_type: p for p in attribute_diff.properties}
    property_diff = properties_by_type[DatabaseEdgeType.IS_PROTECTED]
    assert property_diff.property_type == DatabaseEdgeType.IS_PROTECTED
    assert property_diff.previous_value is False
    assert property_diff.new_value is True
    assert property_diff.action is DiffAction.UPDATED
    assert before_change < property_diff.changed_at < after_change


async def test_attribute_branch_set_null(db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    car_branch.nbr_seats.value = None
    before_change = Timestamp()
    await car_branch.save(db=db)
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
    assert node_diff.uuid == car_accord_main.id
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
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


async def test_attribute_branch_update_from_null(
    db: InfrahubDatabase, default_branch: Branch, person_john_main: Node
) -> None:
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="accord", is_electric=False, owner=person_john_main.id)
    await car.save(db=db)
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car.id)
    car_branch.nbr_seats.value = 5
    before_change = Timestamp()
    await car_branch.save(db=db)
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
    assert node_diff.uuid == car.id
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "nbr_seats"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == "NULL"
    assert property_diff.new_value == 5
    assert property_diff.action is DiffAction.ADDED
    assert before_change < property_diff.changed_at < after_change


async def test_attribute_property_multiple_branch_updates(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
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
    assert len(root_path.nodes) == 1
    node_diff = root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 3
    node_diff.attributes.sort(key=lambda da: da.name, reverse=True)
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Alfred Four"
    assert before_last_change < property_diff.changed_at < after_last_change
    attribute_diff = node_diff.attributes[1]
    assert attribute_diff.name == "human_friendly_id"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == '["Alfred"]'
    assert property_diff.new_value == '["Alfred Four"]'
    assert before_last_change < property_diff.changed_at < after_last_change


async def test_attribute_property_branch_create_multiple_updates(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name="Gerald", height=160)
    await person.save(db=db)
    after_create = Timestamp()
    person.name.value = "Gerald Two"
    await person.save(db=db)
    person.name.value = "Gerald Three"
    await person.save(db=db)
    before_last_change = Timestamp()
    person.name.value = "Gerald Four"
    await person.save(db=db)
    after_last_change = Timestamp()

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
    assert len(root_path.nodes) == 1
    node_diff = root_path.nodes[0]
    assert node_diff.uuid == person.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.ADDED
    assert node_diff.is_node_kind_migration is False
    attributes_by_name = {a.name: a for a in node_diff.attributes}
    assert set(attributes_by_name.keys()) == {"name", "height", "human_friendly_id", "display_label"}
    # name attribute
    attribute_diff = attributes_by_name["name"]
    assert attribute_diff.action is DiffAction.ADDED
    prop_diffs_by_type = {p.property_type: p for p in attribute_diff.properties}
    assert set(prop_diffs_by_type.keys()) == {
        DatabaseEdgeType.HAS_VALUE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.HAS_VALUE, "Gerald Four"),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        property_diff = prop_diffs_by_type[prop_type]
        assert property_diff.action is DiffAction.ADDED
        assert property_diff.previous_value is None
        assert property_diff.new_value == new_value
        if prop_type is DatabaseEdgeType.HAS_VALUE:
            assert before_last_change < property_diff.changed_at < after_last_change
        else:
            assert from_time < property_diff.changed_at < after_create
    # height attribute
    attribute_diff = attributes_by_name["height"]
    assert attribute_diff.action is DiffAction.ADDED
    prop_diffs_by_type = {p.property_type: p for p in attribute_diff.properties}
    assert set(prop_diffs_by_type.keys()) == {
        DatabaseEdgeType.HAS_VALUE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.HAS_VALUE, 160),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        property_diff = prop_diffs_by_type[prop_type]
        assert property_diff.action is DiffAction.ADDED
        assert property_diff.previous_value is None
        assert property_diff.new_value == new_value
        assert from_time < property_diff.changed_at < after_create


async def test_update_attribute_under_agnostic_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    fruit_tag_schema_global: SchemaRoot,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    fruit_1 = await Node.init(db=db, schema="GardenFruit", branch=branch)
    await fruit_1.new(db=db, name="blueberry", branch_aware_attr="branchval")
    await fruit_1.save(db=db)

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
    assert set(diff_nodes_by_id.keys()) == {fruit_1.get_id()}
    diff_node_fruit = diff_nodes_by_id[fruit_1.get_id()]
    assert diff_node_fruit.action is DiffAction.UPDATED
    assert diff_node_fruit.is_node_kind_migration is False
    assert len(diff_node_fruit.relationships) == 0
    assert len(diff_node_fruit.attributes) == 1
    attr_diff = diff_node_fruit.attributes.pop()
    assert attr_diff.name == "branch_aware_attr"
    assert attr_diff.action is DiffAction.ADDED
    properties_by_type = {p.property_type: p for p in attr_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.HAS_VALUE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for property_type, new_value in (
        (DatabaseEdgeType.HAS_VALUE, "branchval"),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[property_type]
        assert prop_diff.action is DiffAction.ADDED
        assert prop_diff.previous_value is None
        assert prop_diff.new_value == new_value


@pytest.mark.parametrize("new_source,expected_action", [(True, DiffAction.UPDATED), (False, DiffAction.REMOVED)])
async def test_diff_attribute_single_source_property_change(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    person_alfred_main: Node,
    person_jane_main: Node,
    new_source: bool,
    expected_action: DiffAction,
) -> None:
    """Test that updating or removing a HAS_SOURCE property from an attribute on a branch is captured in the diff."""
    # Set a source on john's name attribute on main
    john_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_john_main.id)
    john_main.name.source = person_alfred_main
    await john_main.save(db=db)

    # Create a branch after the source is set
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)

    # On the branch, update or clear the source from the name attribute
    john_branch = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
    if new_source:
        john_branch.name.source = person_jane_main
    else:
        john_branch.name.clear_source()
    await john_branch.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    # No changes on main
    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.nodes == []

    # Branch should show the source change
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    node_diff = branch_root_path.nodes[0]
    assert node_diff.uuid == person_john_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED

    # Find the name attribute diff
    attrs_by_name = {a.name: a for a in node_diff.attributes}
    assert "name" in attrs_by_name
    name_attr_diff = attrs_by_name["name"]
    assert name_attr_diff.action is DiffAction.UPDATED

    # Verify that the HAS_SOURCE property change is included
    props_by_type = {p.property_type: p for p in name_attr_diff.properties}
    assert DatabaseEdgeType.HAS_SOURCE in props_by_type
    source_prop = props_by_type[DatabaseEdgeType.HAS_SOURCE]
    assert source_prop.action is expected_action
    assert source_prop.previous_value == person_alfred_main.get_id()
    if new_source:
        assert source_prop.new_value == person_jane_main.get_id()
    else:
        assert source_prop.new_value is None


async def test_attribute_property_new_value_differs_per_branch_on_multi_change_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    person_john_main: Node,
    person_alfred_main: Node,
) -> None:
    """Validate diff for conflicting source updates on relationships."""
    branch = await create_branch(db=db, branch_name="branch-prop-new-value-per-branch")
    from_time = Timestamp(branch.created_at)

    # Branch changes: color=#RED and name.source = alfred
    branch_car = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    branch_car.color.value = "#RED"
    branch_car.name.source = person_alfred_main
    await branch_car.save(db=db)

    # Main changes (after branch fork): color=#BAD and name.source = john
    main_car = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    main_car.color.value = "#BAD"
    main_car.name.source = person_john_main
    await main_car.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    def _name_source_new_value(diff_root: DiffRoot) -> str | None:
        for node in diff_root.nodes:
            if node.uuid != car_accord_main.id:
                continue
            for attr in node.attributes:
                if attr.name != "name":
                    continue
                for prop in attr.properties:
                    if prop.property_type is DatabaseEdgeType.HAS_SOURCE:
                        return prop.new_value
        return None

    base_new = _name_source_new_value(calculated_diffs.base_branch_diff)
    branch_new = _name_source_new_value(calculated_diffs.diff_branch_diff)

    assert base_new == person_john_main.id, f"base-branch diff should report name.source.new_value=john, got {base_new}"
    assert branch_new == person_alfred_main.id, (
        f"diff-branch diff should report name.source.new_value=alfred, got {branch_new}"
    )
