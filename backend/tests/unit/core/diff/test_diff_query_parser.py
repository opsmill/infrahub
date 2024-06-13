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


async def test_node_branch_delete(db: InfrahubDatabase, default_branch: Branch, car_accord_main):
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
    assert len(branch_root_path.nodes) == 1
    node_diff = branch_root_path.nodes[0]
    assert node_diff.uuid == car_accord_main.id
    assert node_diff.kind == "TestCar"
    assert node_diff.action is DiffAction.REMOVED
    assert len(node_diff.attributes) == 5
    attributes_by_name = {attr.name: attr for attr in node_diff.attributes}
    assert set(attributes_by_name.keys()) == {"name", "nbr_seats", "color", "is_electric", "transmission"}
    for attribute_name in attributes_by_name:
        attribute_diff = attributes_by_name[attribute_name]
        assert attribute_diff.action is DiffAction.REMOVED
        properties_by_type = {prop.property_type: prop for prop in attribute_diff.properties}
        diff_property = properties_by_type["HAS_VALUE"]
        assert diff_property.action is DiffAction.REMOVED
        assert diff_property.new_value is None


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
