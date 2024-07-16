from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction
from infrahub.core.diff.query_parser import DiffQueryParser
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.diff import DiffAllPathsQuery
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

    diff_query = await DiffAllPathsQuery.init(
        db=db,
        branch=branch,
        base_branch=default_branch,
    )
    await diff_query.execute(db=db)
    diff_parser = DiffQueryParser(
        diff_query=diff_query, base_branch_name=default_branch.name, schema_manager=registry.schema, from_time=from_time
    )
    diff_parser.parse()

    assert diff_parser.get_branches() == {default_branch.name, branch.name}
    main_root_path = diff_parser.get_diff_root_for_branch(branch=default_branch.name)
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
    assert property_diff.property_type == "HAS_VALUE"
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Big Alfred"
    assert property_diff.action is DiffAction.UPDATED
    assert main_before_change < property_diff.changed_at < main_after_change
    branch_root_path = diff_parser.get_diff_root_for_branch(branch=branch.name)
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
    assert property_diff.property_type == "HAS_VALUE"
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

    diff_query = await DiffAllPathsQuery.init(
        db=db,
        branch=default_branch,
        base_branch=default_branch,
        diff_from=from_time,
    )
    await diff_query.execute(db=db)
    diff_parser = DiffQueryParser(
        diff_query=diff_query, base_branch_name=default_branch.name, schema_manager=registry.schema, from_time=from_time
    )
    diff_parser.parse()

    assert diff_parser.get_branches() == {default_branch.name}
    main_root_path = diff_parser.get_diff_root_for_branch(branch=default_branch.name)
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
    property_diff = properties_by_type["IS_VISIBLE"]
    assert property_diff.property_type == "IS_VISIBLE"
    assert property_diff.previous_value is True
    assert property_diff.new_value is False
    assert property_diff.action is DiffAction.UPDATED
    assert before_change < property_diff.changed_at < after_change
    property_diff = properties_by_type["IS_PROTECTED"]
    assert property_diff.property_type == "IS_PROTECTED"
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

    diff_query = await DiffAllPathsQuery.init(
        db=db,
        branch=branch,
        base_branch=default_branch,
    )
    await diff_query.execute(db=db)
    diff_parser = DiffQueryParser(
        diff_query=diff_query, base_branch_name=default_branch.name, schema_manager=registry.schema, from_time=from_time
    )
    diff_parser.parse()

    assert diff_parser.get_branches() == {branch.name}
    branch_root_path = diff_parser.get_diff_root_for_branch(branch=branch.name)
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
    assert property_diff.property_type == "HAS_VALUE"
    assert property_diff.previous_value == 5
    assert property_diff.new_value == "NULL"
    assert property_diff.action is DiffAction.REMOVED
    assert before_change < property_diff.changed_at < after_change


async def test_node_branch_delete(db: InfrahubDatabase, default_branch: Branch, car_accord_main, person_john_main):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await car_branch.delete(db=db)

    diff_query = await DiffAllPathsQuery.init(
        db=db,
        branch=branch,
        base_branch=default_branch,
    )
    await diff_query.execute(db=db)
    diff_parser = DiffQueryParser(
        diff_query=diff_query, base_branch_name=default_branch.name, schema_manager=registry.schema, from_time=from_time
    )
    diff_parser.parse()

    assert diff_parser.get_branches() == {branch.name}
    branch_root_path = diff_parser.get_diff_root_for_branch(branch=branch.name)
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
        diff_property = properties_by_type["HAS_VALUE"]
        assert diff_property.action is DiffAction.REMOVED
        assert diff_property.new_value is None
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


async def test_node_branch_add(db: InfrahubDatabase, default_branch: Branch, car_accord_main):
    branch = await create_branch(db=db, branch_name="branch")
    from_time = Timestamp(branch.created_at)
    new_person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await new_person.new(db=db, name="Stokely")
    before_change = Timestamp()
    await new_person.save(db=db)
    after_change = Timestamp()

    diff_query = await DiffAllPathsQuery.init(
        db=db,
        branch=branch,
        base_branch=default_branch,
    )
    await diff_query.execute(db=db)
    diff_parser = DiffQueryParser(
        diff_query=diff_query, base_branch_name=default_branch.name, schema_manager=registry.schema, from_time=from_time
    )
    diff_parser.parse()

    assert diff_parser.get_branches() == {branch.name}
    branch_root_path = diff_parser.get_diff_root_for_branch(branch=branch.name)
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
    diff_property = properties_by_type["HAS_VALUE"]
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

    diff_query = await DiffAllPathsQuery.init(
        db=db,
        branch=branch,
        base_branch=default_branch,
    )
    await diff_query.execute(db=db)
    diff_parser = DiffQueryParser(
        diff_query=diff_query, base_branch_name=default_branch.name, schema_manager=registry.schema, from_time=from_time
    )
    diff_parser.parse()

    assert diff_parser.get_branches() == {branch.name}
    root_path = diff_parser.get_diff_root_for_branch(branch=branch.name)
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
    assert property_diff.property_type == "HAS_VALUE"
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Alfred Four"
    assert before_last_change < property_diff.changed_at < after_last_change


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

    diff_query = await DiffAllPathsQuery.init(
        db=db,
        branch=branch,
        base_branch=default_branch,
    )
    await diff_query.execute(db=db)
    diff_parser = DiffQueryParser(
        diff_query=diff_query, base_branch_name=default_branch.name, schema_manager=registry.schema, from_time=from_time
    )
    diff_parser.parse()

    assert diff_parser.get_branches() == {branch.name, default_branch.name}
    root_path = diff_parser.get_diff_root_for_branch(branch=branch.name)
    assert root_path.branch == branch.name
    assert len(root_path.nodes) == 1
    node_diff = root_path.nodes[0]
    assert node_diff.uuid == car_accord_main.id
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes) == 0
    assert len(node_diff.relationships) == 1
    relationship_diff = node_diff.relationships[0]
    assert relationship_diff.name == "owner"
    assert relationship_diff.action is DiffAction.UPDATED
    assert len(relationship_diff.relationships) == 1
    single_relationship = relationship_diff.relationships[0]
    assert single_relationship.peer_id == person_john_main.id
    assert single_relationship.action is DiffAction.UPDATED
    assert len(single_relationship.properties) == 2
    property_diff_by_type = {p.property_type: p for p in single_relationship.properties}
    property_diff = property_diff_by_type["IS_VISIBLE"]
    assert property_diff.property_type == "IS_VISIBLE"
    assert property_diff.previous_value is True
    assert property_diff.new_value is False
    assert before_branch_change < property_diff.changed_at < after_branch_change
    property_diff = property_diff_by_type["IS_RELATED"]
    assert property_diff.property_type == "IS_RELATED"
    assert property_diff.previous_value == person_john_main.id
    assert property_diff.new_value == person_john_main.id
    assert property_diff.changed_at < before_branch_change
    root_main_path = diff_parser.get_diff_root_for_branch(branch=default_branch.name)
    assert root_main_path.branch == default_branch.name
    assert len(root_main_path.nodes) == 3
    diff_nodes_by_id = {n.uuid: n for n in root_main_path.nodes}
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
    single_relationship_diff = relationship_diff.relationships[0]
    assert single_relationship_diff.peer_id == car_accord_main.id
    assert single_relationship_diff.action is DiffAction.ADDED
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
    property_diff = property_diff_by_type["IS_RELATED"]
    assert property_diff.property_type == "IS_RELATED"
    assert property_diff.previous_value is None
    assert property_diff.new_value == person_jane_main.id
    assert property_diff.action is DiffAction.ADDED
    assert before_main_change < property_diff.changed_at < after_main_change
    property_diff = property_diff_by_type["IS_VISIBLE"]
    assert property_diff.property_type == "IS_VISIBLE"
    assert property_diff.previous_value is None
    assert property_diff.new_value is True
    assert property_diff.action is DiffAction.ADDED
    assert before_main_change < property_diff.changed_at < after_main_change
    property_diff = property_diff_by_type["IS_PROTECTED"]
    assert property_diff.property_type == "IS_PROTECTED"
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
    property_diff = property_diff_by_type["IS_RELATED"]
    assert property_diff.property_type == "IS_RELATED"
    assert property_diff.previous_value == person_john_main.id
    assert property_diff.new_value is None
    assert property_diff.action is DiffAction.REMOVED
    assert before_main_change < property_diff.changed_at < after_main_change
    property_diff = property_diff_by_type["IS_VISIBLE"]
    assert property_diff.property_type == "IS_VISIBLE"
    assert property_diff.previous_value is True
    assert property_diff.new_value is None
    assert property_diff.action is DiffAction.REMOVED
    assert before_main_change < property_diff.changed_at < after_main_change
    property_diff = property_diff_by_type["IS_PROTECTED"]
    assert property_diff.property_type == "IS_PROTECTED"
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

    diff_query = await DiffAllPathsQuery.init(
        db=db,
        branch=branch,
        base_branch=default_branch,
    )
    await diff_query.execute(db=db)
    diff_parser = DiffQueryParser(
        diff_query=diff_query, base_branch_name=default_branch.name, schema_manager=registry.schema, from_time=from_time
    )
    diff_parser.parse()

    assert diff_parser.get_branches() == {branch.name}
    root_path = diff_parser.get_diff_root_for_branch(branch=branch.name)
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
    assert {p.property_type for p in single_relationship.properties} == {"IS_RELATED", "IS_VISIBLE", "IS_PROTECTED"}
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
        ("IS_VISIBLE", DiffAction.ADDED, True, None),
        ("IS_PROTECTED", DiffAction.ADDED, False, None),
        ("HAS_VALUE", DiffAction.ADDED, "Batmobile", None),
    }
    attribute_diff = attributes_by_name["color"]
    assert len(attribute_diff.properties) == 3
    assert {(p.property_type, p.action, p.new_value, p.previous_value) for p in attribute_diff.properties} == {
        ("IS_VISIBLE", DiffAction.ADDED, True, None),
        ("IS_PROTECTED", DiffAction.ADDED, False, None),
        ("HAS_VALUE", DiffAction.ADDED, "#000000", None),
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
        ("IS_VISIBLE", DiffAction.ADDED, True, None),
        ("IS_PROTECTED", DiffAction.ADDED, False, None),
        ("IS_RELATED", DiffAction.ADDED, person_jane_main.id, None),
    }
