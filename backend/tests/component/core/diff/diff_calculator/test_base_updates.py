from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.calculator import DiffCalculator
from infrahub.core.diff.model.field_specifiers_map import NodeFieldSpecifierMap
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


async def test_diff_attribute_branch_update_with_previous_base_update_ignored(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
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
    node_field_specifiers = NodeFieldSpecifierMap()
    node_field_specifiers.add_entry(node_uuid=alfred_main.id, kind=alfred_main.get_kind(), field_name="name")
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
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    node_diff = branch_root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    node_diff.attributes.sort(key=lambda da: da.name, reverse=True)
    assert len(node_diff.attributes) == 3
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


async def test_diff_attribute_branch_update_with_concurrent_base_update_captured(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
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
    node_field_specifiers = NodeFieldSpecifierMap()
    node_field_specifiers.add_entry(node_uuid=alfred_main.id, kind=alfred_main.get_kind(), field_name="name")
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
    node_diff = base_root_path.nodes[0]
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
    assert base_before_change < property_diff.changed_at < base_after_change
    attribute_diff = node_diff.attributes[1]
    assert attribute_diff.name == "human_friendly_id"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == '["Alfred"]'
    assert property_diff.new_value == '["Big Alfred"]'
    assert property_diff.action is DiffAction.UPDATED
    assert base_before_change < property_diff.changed_at < base_after_change
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


async def test_diff_attribute_branch_update_with_previous_base_update_captured(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
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
        include_unchanged=False,
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.branch == default_branch.name
    assert len(base_root_path.nodes) == 1
    node_diff = base_root_path.nodes[0]
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
    assert base_before_change < property_diff.changed_at < base_after_change
    attribute_diff = node_diff.attributes[1]
    assert attribute_diff.name == "human_friendly_id"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == '["Alfred"]'
    assert property_diff.new_value == '["Big Alfred"]'
    assert property_diff.action is DiffAction.UPDATED
    assert base_before_change < property_diff.changed_at < base_after_change
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


async def test_diff_attribute_branch_update_with_separate_previous_base_update_captured(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
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
    node_field_specifiers = NodeFieldSpecifierMap()
    node_field_specifiers.add_entry(node_uuid=alfred_main.id, kind=alfred_main.get_kind(), field_name="name")
    node_field_specifiers.add_entry(
        node_uuid=alfred_main.id, kind=alfred_main.get_kind(), field_name="human_friendly_id"
    )
    node_field_specifiers.add_entry(node_uuid=car_accord_main.id, kind=car_accord_main.get_kind(), field_name="color")
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
    nodes_by_id = {n.uuid: n for n in base_root_path.nodes}
    assert set(nodes_by_id.keys()) == {car_accord_main.id, person_alfred_main.id}
    # car on main
    node_diff = nodes_by_id[car_accord_main.id]
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.relationships) == 0
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
    # alfred on main
    node_diff = nodes_by_id[person_alfred_main.id]
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.relationships) == 0
    assert len(node_diff.attributes) == 3
    node_diff.attributes.sort(key=lambda da: da.name, reverse=True)
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UNCHANGED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Alfred"
    assert property_diff.action is DiffAction.UNCHANGED
    attribute_diff = node_diff.attributes[1]
    assert attribute_diff.name == "human_friendly_id"
    assert attribute_diff.action is DiffAction.UNCHANGED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == '["Alfred"]'
    assert property_diff.new_value == '["Alfred"]'
    assert property_diff.action is DiffAction.UNCHANGED

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


async def test_branch_node_delete_with_base_updates(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, person_john_main: Node, person_jane_main: Node
) -> None:
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
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    base_root_path = calculated_diffs.base_branch_diff
    assert base_root_path.branch == default_branch.name
    node_diffs_by_id = {n.uuid: n for n in base_root_path.nodes}
    assert set(node_diffs_by_id.keys()) == {car_accord_main.id, person_john_main.id}
    node_diff = node_diffs_by_id[car_accord_main.id]
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
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
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_PROTECTED, False),
        (DatabaseEdgeType.IS_RELATED, person_jane_main.id),
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
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_PROTECTED, False),
        (DatabaseEdgeType.IS_RELATED, person_john_main.id),
    ):
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.action is DiffAction.REMOVED
        assert diff_prop.previous_value == previous_value
        assert diff_prop.new_value is None
    peer_node_diff = node_diffs_by_id[person_john_main.id]
    assert peer_node_diff.action is DiffAction.UPDATED
    assert peer_node_diff.is_node_kind_migration is False
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
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_PROTECTED, False),
        (DatabaseEdgeType.IS_RELATED, car_accord_main.id),
    ):
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.action is DiffAction.REMOVED
        assert diff_prop.previous_value == previous_value
        assert diff_prop.new_value is None
    attributes_by_name = {attr.name: attr for attr in node_diff.attributes}
    assert set(attributes_by_name.keys()) == {"color", "display_label"}
    attribute_diff = attributes_by_name["color"]
    assert attribute_diff.action is DiffAction.UPDATED
    properties_by_type = {prop.property_type: prop for prop in attribute_diff.properties}
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.HAS_VALUE}
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


async def test_branch_relationship_delete_with_property_update(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
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
    await dog_main.best_friend.update(db=db, data={"id": persons[0].id, "_relation__is_protected": True})
    await dog_main.save(db=db)
    after_main_change = Timestamp()

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    base_diff = calculated_diffs.base_branch_diff
    assert base_diff.branch == default_branch.name
    node_diffs_by_id = {n.uuid: n for n in base_diff.nodes}
    node_diff = node_diffs_by_id[dog_main.id]
    assert node_diff.uuid == dog_main.id
    assert node_diff.kind == "TestDog"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
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
    assert set(prop_diff_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    is_protected_prop = prop_diff_by_type[DatabaseEdgeType.IS_PROTECTED]
    assert is_protected_prop.action is DiffAction.UPDATED
    assert is_protected_prop.new_value is True
    assert is_protected_prop.previous_value is False
    assert before_main_change < is_protected_prop.changed_at < after_main_change
    diff_prop = prop_diff_by_type[DatabaseEdgeType.IS_RELATED]
    assert diff_prop.action is DiffAction.UNCHANGED
    assert diff_prop.new_value == persons[0].id
    assert diff_prop.previous_value == persons[0].id
    assert diff_prop.changed_at < from_time

    branch_diff = calculated_diffs.diff_branch_diff
    assert branch_diff.branch == branch.name
    node_diffs_by_id = {n.uuid: n for n in branch_diff.nodes}
    assert set(node_diffs_by_id.keys()) == {dog_branch.id, persons[0].id}
    dog_node = node_diffs_by_id[dog_branch.id]
    assert dog_node.action is DiffAction.UPDATED
    assert dog_node.is_node_kind_migration is False
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
    assert len(prop_diff_by_type) == 2
    for property_type, previous_value in [
        (DatabaseEdgeType.IS_RELATED, persons[0].id),
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
    assert len(prop_diff_by_type) == 2
    for property_type, previous_value in [
        (DatabaseEdgeType.IS_RELATED, dog_branch.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        prop_diff = prop_diff_by_type[property_type]
        assert prop_diff.action is DiffAction.REMOVED
        assert prop_diff.new_value is None
        assert prop_diff.previous_value == previous_value
        assert before_branch_change < prop_diff.changed_at < after_branch_change


async def test_node_deleted_on_base_update_on_branch(
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
    alfred_branch.name.value = "Still Alfred"
    await alfred_branch.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    # deleted on base
    diff_root = calculated_diffs.base_branch_diff
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
    # update on branch
    diff_root = calculated_diffs.diff_branch_diff
    assert len(diff_root.nodes) == 1
    diff_node = diff_root.nodes.pop()
    assert diff_node.action is DiffAction.UPDATED
    assert diff_node.uuid == person_alfred_main.id
    assert diff_node.is_node_kind_migration is False
    attributes_by_name = {a.name: a for a in diff_node.attributes}
    assert set(attributes_by_name.keys()) == {"display_label", "human_friendly_id", "name"}
    diff_node.attributes.sort(key=lambda da: da.name, reverse=True)
    attr_diff = diff_node.attributes[0]
    assert attr_diff.name == "name"
    assert attr_diff.action is DiffAction.UPDATED
    props_by_type = {p.property_type: p for p in attr_diff.properties}
    assert set(props_by_type.keys()) == {DatabaseEdgeType.HAS_VALUE}
    prop_diff = attr_diff.properties[0]
    assert prop_diff.action is DiffAction.UPDATED
    assert prop_diff.previous_value == "Alfred"
    assert prop_diff.new_value == "Still Alfred"
    attr_diff = diff_node.attributes[1]
    assert attr_diff.name == "human_friendly_id"
    assert attr_diff.action is DiffAction.UPDATED
    props_by_type = {p.property_type: p for p in attr_diff.properties}
    assert set(props_by_type.keys()) == {DatabaseEdgeType.HAS_VALUE}
    prop_diff = attr_diff.properties[0]
    assert prop_diff.action is DiffAction.UPDATED
    assert prop_diff.previous_value == '["Alfred"]'
    assert prop_diff.new_value == '["Still Alfred"]'
    assert len(diff_node.relationships) == 0


async def test_relationship_updated_then_node_deleted(
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
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    branch_diff_root = calculated_diffs.diff_branch_diff
    nodes_by_id = {n.uuid: n for n in branch_diff_root.nodes}
    assert set(nodes_by_id.keys()) == {car_camry_main.id, person_jane_main.id}
    car_base_diff = nodes_by_id[car_camry_main.id]
    assert car_base_diff.action is DiffAction.REMOVED
    assert car_base_diff.is_node_kind_migration is False
    attributes_by_name = {a.name: a for a in car_base_diff.attributes}
    assert set(attributes_by_name.keys()) == {
        "color",
        "display_label",
        "nbr_seats",
        "transmission",
        "is_electric",
        "name",
        "human_friendly_id",
    }
    for attr_diff in attributes_by_name.values():
        assert attr_diff.action is DiffAction.REMOVED
        properties_by_type = {p.property_type: p for p in attr_diff.properties}
        assert set(properties_by_type.keys()) == {
            DatabaseEdgeType.HAS_VALUE,
            DatabaseEdgeType.IS_PROTECTED,
        }

        if attr_diff.name in ["display_label", "human_friendly_id"]:
            # HFID or display_label don't work with getattr
            continue

        for prop_type, previous_value in (
            (DatabaseEdgeType.HAS_VALUE, getattr(car_main, attr_diff.name).value),
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
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_RELATED, person_jane_main.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[prop_type]
        assert prop_diff.action is DiffAction.REMOVED
        assert prop_diff.previous_value == previous_value
        assert prop_diff.new_value in (None, "NULL")
    person_base_diff = nodes_by_id[person_jane_main.id]
    assert person_base_diff.action is DiffAction.UPDATED
    assert person_base_diff.is_node_kind_migration is False
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
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
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
    assert car_base_diff.is_node_kind_migration is False
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
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_RELATED, person_jane_main.id),
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
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_RELATED, person_alfred_main.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[prop_type]
        assert prop_diff.action is DiffAction.ADDED
        assert prop_diff.previous_value in (None, "NULL")
        assert prop_diff.new_value == new_value

    person_base_diff = nodes_by_id[person_jane_main.id]
    assert person_base_diff.action is DiffAction.UPDATED
    assert person_base_diff.is_node_kind_migration is False
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
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[prop_type]
        assert prop_diff.action is DiffAction.REMOVED
        assert prop_diff.previous_value == previous_value
        assert prop_diff.new_value in (None, "NULL")


async def test_property_update_then_relationship_deleted(
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
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    await car_branch.owner.update(db=db, data={"id": person_jane_main.id, "_relation__owner": person_alfred_main.id})
    await car_branch.save(db=db)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    await car_branch.owner.update(db=db, data={"id": person_john_main.id})
    await car_branch.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    branch_diff_root = calculated_diffs.diff_branch_diff
    nodes_by_id = {n.uuid: n for n in branch_diff_root.nodes}
    assert set(nodes_by_id.keys()) == {person_jane_main.id, person_john_main.id, car_camry_main.id}
    car_branch_diff = nodes_by_id[car_camry_main.id]
    assert car_branch_diff.action is DiffAction.UPDATED
    assert car_branch_diff.is_node_kind_migration is False
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
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_RELATED, person_jane_main.id),
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
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_RELATED, person_john_main.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[prop_type]
        assert prop_diff.action is DiffAction.ADDED
        assert prop_diff.previous_value in (None, "NULL")
        assert prop_diff.new_value == new_value

    person_removed_branch_diff = nodes_by_id[person_jane_main.id]
    assert person_removed_branch_diff.action is DiffAction.UPDATED
    assert person_removed_branch_diff.is_node_kind_migration is False
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
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[prop_type]
        assert prop_diff.action is DiffAction.REMOVED
        assert prop_diff.previous_value == previous_value
        assert prop_diff.new_value in (None, "NULL")

    person_added_branch_diff = nodes_by_id[person_john_main.id]
    assert person_added_branch_diff.action is DiffAction.UPDATED
    assert person_added_branch_diff.is_node_kind_migration is False
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
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        prop_diff = properties_by_type[prop_type]
        assert prop_diff.action is DiffAction.ADDED
        assert prop_diff.previous_value in (None, "NULL")
        assert prop_diff.new_value == new_value

    base_diff_root = calculated_diffs.base_branch_diff
    assert base_diff_root.nodes == []


async def test_diff_unchanged_included_when_not_first_diff(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
) -> None:
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
    alfred_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_alfred_main.id)
    alfred_main.name.value = "Alfred"
    await alfred_main.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    node_field_specifiers = NodeFieldSpecifierMap()
    node_field_specifiers.add_entry(node_uuid=alfred_main.id, kind=alfred_main.get_kind(), field_name="name")
    node_field_specifiers.add_entry(node_uuid=car_accord_main.id, kind=car_accord_main.get_kind(), field_name="color")
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
    assert len(base_root_path.nodes) == 2
    nodes_by_id = {n.uuid: n for n in base_root_path.nodes}
    # car on main
    node_diff = nodes_by_id[car_accord_main.id]
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
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
    # person on main
    node_diff = nodes_by_id[person_alfred_main.id]
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UNCHANGED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.attributes) == 3
    node_diff.attributes.sort(key=lambda da: da.name, reverse=True)
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UNCHANGED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Alfred"
    assert property_diff.action is DiffAction.UNCHANGED
    attribute_diff = node_diff.attributes[1]
    assert attribute_diff.name == "human_friendly_id"
    assert attribute_diff.action is DiffAction.UNCHANGED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == '["Alfred"]'
    assert property_diff.new_value == '["Alfred"]'
    assert property_diff.action is DiffAction.UNCHANGED

    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    # person on branch
    node_diff = branch_root_path.nodes[0]
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
