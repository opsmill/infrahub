from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction
from infrahub.core.diff.query_parser import DiffQueryParser
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
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
    await alfred_main.save(db=db)
    alfred_branch = await NodeManager.get_one(db=db, branch=branch, id=person_alfred_main.id)
    alfred_branch.name.value = "Little Alfred"
    await alfred_branch.save(db=db)

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
    assert len(main_root_path.nodes_by_id) == 1
    node_diff = main_root_path.nodes_by_id[person_alfred_main.id]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes_by_name) == 1
    attribute_diff = node_diff.attributes_by_name["name"]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties_by_type) == 1
    property_diff = attribute_diff.properties_by_type["HAS_VALUE"]
    assert property_diff.property_type == "HAS_VALUE"
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Big Alfred"
    assert property_diff.get_diff_action(from_time=from_time) is DiffAction.UPDATED
    branch_root_path = diff_parser.get_diff_root_for_branch(branch=branch.name)
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes_by_id) == 1
    node_diff = branch_root_path.nodes_by_id[person_alfred_main.id]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes_by_name) == 1
    attribute_diff = node_diff.attributes_by_name["name"]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties_by_type) == 1
    property_diff = attribute_diff.properties_by_type["HAS_VALUE"]
    assert property_diff.property_type == "HAS_VALUE"
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Little Alfred"
    assert property_diff.get_diff_action(from_time=from_time) is DiffAction.UPDATED


async def test_attribute_property_main_update(
    db: InfrahubDatabase, default_branch: Branch, person_alfred_main, person_john_main, car_accord_main
):
    from_time = Timestamp()
    alfred_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_alfred_main.id)
    alfred_main.name.is_visible = False
    alfred_main.name.is_protected = True
    await alfred_main.save(db=db)

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
    assert len(main_root_path.nodes_by_id) == 1
    node_diff = main_root_path.nodes_by_id[person_alfred_main.id]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes_by_name) == 1
    attribute_diff = node_diff.attributes_by_name["name"]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties_by_type) == 2
    property_diff = attribute_diff.properties_by_type["IS_VISIBLE"]
    assert property_diff.property_type == "IS_VISIBLE"
    assert property_diff.previous_value is True
    assert property_diff.new_value is False
    assert property_diff.get_diff_action(from_time=from_time) is DiffAction.UPDATED
    property_diff = attribute_diff.properties_by_type["IS_PROTECTED"]
    assert property_diff.property_type == "IS_PROTECTED"
    assert property_diff.previous_value is False
    assert property_diff.new_value is True
    assert property_diff.get_diff_action(from_time=from_time) is DiffAction.UPDATED


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
    assert len(root_path.nodes_by_id) == 1
    node_diff = root_path.nodes_by_id[person_alfred_main.id]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert len(node_diff.attributes_by_name) == 1
    attribute_diff = node_diff.attributes_by_name["name"]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UPDATED
    assert len(attribute_diff.properties_by_type) == 1
    property_diff = attribute_diff.properties_by_type["HAS_VALUE"]
    assert property_diff.property_type == "HAS_VALUE"
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Alfred Four"
    assert property_diff.previous_value_changed_at < from_time
    assert before_last_change < property_diff.new_value_changed_at < after_last_change
