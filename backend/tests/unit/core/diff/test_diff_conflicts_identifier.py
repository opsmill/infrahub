from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, PathType
from infrahub.core.diff.conflicts_identifier import DiffConflictsIdentifier
from infrahub.core.diff.model.diff import BranchChanges, DataConflict
from infrahub.core.diff.query_parser import DiffQueryParser
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.query.diff import DiffAllPathsQuery
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


async def test_diff_path_conflict_attribute_branch_update(
    db: InfrahubDatabase, default_branch: Branch, person_alfred_main, person_john_main, car_accord_main
):
    branch = await create_branch(db=db, branch_name="branch")
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
    diff_index = DiffQueryParser(diff_query=diff_query)
    diff_index.parse()
    root_paths = diff_index.get_all_root_paths()
    conflict_identifier = DiffConflictsIdentifier(
        schema_manager=registry.schema, base_branch=default_branch.name, from_time=Timestamp(branch.created_at)
    )

    assert len(root_paths) == 1
    conflicts = conflict_identifier.get_conflicts_for_path(root_path=root_paths[0])
    assert len(conflicts) == 1
    assert set(conflicts[0].changes) == {
        BranchChanges(previous="Alfred", new="Big Alfred", branch="main", action=DiffAction.ADDED),
        BranchChanges(previous="Alfred", new="Little Alfred", branch="branch", action=DiffAction.ADDED),
    }
    conflicts[0].changes = []
    assert conflicts[0] == DataConflict(
        name="name",
        type="data",
        kind="TestPerson",
        id=alfred_branch.id,
        conflict_path=f"data/{alfred_branch.id}/name/value",
        path=f"data/{alfred_branch.id}/name/value",
        path_type=PathType.ATTRIBUTE,  #: P
        property_name="HAS_VALUE",  #: Optional[str]
        change_type="attribute_value",
        changes=[],
    )


async def test_diff_path_conflict_relationship_one_branch_update(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main,
    person_jane_main,
    person_john_main,
    car_accord_main,
):
    branch = await create_branch(db=db, branch_name="branch")
    car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    await car_main.owner.update(db=db, data=person_jane_main)
    await car_main.save(db=db)
    car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await car_branch.owner.update(db=db, data=person_alfred_main)
    await car_branch.save(db=db)

    diff_query = await DiffAllPathsQuery.init(
        db=db,
        branch=branch,
        base_branch=default_branch,
    )
    await diff_query.execute(db=db)
    diff_index = DiffQueryParser(diff_query=diff_query)
    diff_index.parse()
    root_paths = diff_index.get_all_root_paths()
    conflict_identifier = DiffConflictsIdentifier(
        schema_manager=registry.schema, base_branch=default_branch.name, from_time=Timestamp(branch.created_at)
    )

    assert len(root_paths) == 1
    conflicts = conflict_identifier.get_conflicts_for_path(root_path=root_paths[0])
    assert len(conflicts) == 1
    assert set(conflicts[0].changes) == {
        BranchChanges(previous=person_john_main.id, new=person_jane_main.id, branch="main", action=DiffAction.ADDED),
        BranchChanges(
            previous=person_john_main.id, new=person_alfred_main.id, branch=branch.name, action=DiffAction.ADDED
        ),
    }
    # conflicts[0].changes = []
    # assert conflicts[0] == DataConflict(
    #     name="name",
    #     type="data",
    #     kind="TestPerson",
    #     id=alfred_branch.id,
    #     conflict_path=f"data/{alfred_branch.id}/name/value",
    #     path=f"data/{alfred_branch.id}/name/value",
    #     path_type=PathType.ATTRIBUTE, #: P
    #     property_name="HAS_VALUE", #: Optional[str]
    #     change_type="attribute_value",
    #     changes=[]
    # )


# async def test_diff_path_conflict_relationship_many_branch_update(
#     db: InfrahubDatabase,
#     default_branch: Branch,
#     person_alfred_main,
#     person_jane_main,
#     person_john_main,
#     car_accord_main,
#     car_camry_main
# ):
#     branch = await create_branch(db=db, branch_name="branch")
#     car_main = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
#     await car_main.owner.update(db=db, data=person_jane_main)
#     await car_main.save(db=db)
#     car_branch = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
#     await car_branch.owner.update(db=db, data=person_john_main)
#     await car_branch.save(db=db)

#     diff_query = await DiffAllPathsQuery.init(
#         db=db,
#         branch=branch,
#         base_branch=default_branch,
#     )
#     await diff_query.execute(db=db)
#     diff_index = DiffQueryParser(diff_query=diff_query)
#     diff_index.parse()
#     root_paths = diff_index.get_all_root_paths()

#     assert len(root_paths) == 1
#     conflicting_path_groups = root_paths[0].get_conflicting_paths(from_time=branch.created_at)
#     assert len(conflicting_path_groups) == 0


# async def test_diff_element_builder_add_node(db: InfrahubDatabase, default_branch: Branch, person_alfred_main, person_john_main, car_accord_main):
#     branch = await create_branch(db=db, branch_name="branch")
#     new_person = await Node.init(db=db, branch=branch, schema="TestPerson")
#     await new_person.new(db=db, name="New Human")
#     await new_person.save(db=db)
#     diff_element_builder = DiffElementBuilder(from_time=branch.created_at, to_time=current_timestamp())

#     diff_query = await DiffAllPathsQuery.init(
#         db=db,
#         branch=branch,
#         base_branch=default_branch,
#     )
#     await diff_query.execute(db=db)
#     diff_index = DiffQueryParser(diff_query=diff_query)
#     diff_index.parse()
#     root_paths = diff_index.get_all_root_paths()
#     assert len(root_paths) == 1
#     assert root_paths[0].get_conflicting_paths(from_time=branch.created_at) == []
#     root_diff_elements = [diff_element_builder.build_diff_element(root_path=rp) for rp in root_paths]

#     assert len(root_diff_elements) == 1
#     root_diff_element = root_diff_elements[0]
#     assert len(root_diff_element.nodes) == 1
#     node_diff_element = root_diff_element.nodes[new_person.id]
#     assert node_diff_element.branch == branch.name
#     assert set(node_diff_element.labels) == {"TestPerson", "Node", "CoreNode"}
#     assert node_diff_element.kind == "TestPerson"
#     assert node_diff_element.id == new_person.id
#     assert node_diff_element.path == f"data/{new_person.id}"
#     assert node_diff_element.action == DiffAction.ADDED
#     assert len(node_diff_element.attributes) == 2
#     assert set(node_diff_element.attributes.keys()) == {"name", "height"}
#     name_attribute_diff = node_diff_element.attributes["name"]
#     assert name_attribute_diff.name == "name"
#     assert name_attribute_diff.path == f"data/{new_person.id}/name"
#     assert name_attribute_diff.action == DiffAction.ADDED
#     assert len(name_attribute_diff.properties) == 3
#     assert set(name_attribute_diff.properties.keys()) == {"HAS_VALUE", "IS_PROTECTED", "IS_VISIBLE"}
#     name_value_property_diff = name_attribute_diff.properties["HAS_VALUE"]
#     assert name_value_property_diff.branch == branch.name
#     assert name_value_property_diff.type == "HAS_VALUE"
#     assert name_value_property_diff.action == DiffAction.ADDED
#     assert name_value_property_diff.path == f"data/{new_person.id}/name/value"
#     assert name_value_property_diff.value.new == "New Human"
#     assert name_value_property_diff.value.previous is None
#     name_visible_property_diff = name_attribute_diff.properties["IS_VISIBLE"]
#     assert name_visible_property_diff.branch == branch.name
#     assert name_visible_property_diff.type == "IS_VISIBLE"
#     assert name_visible_property_diff.action == DiffAction.ADDED
#     assert name_visible_property_diff.path == f"data/{new_person.id}/name/property/IS_VISIBLE"
#     assert name_visible_property_diff.value.new is True
#     assert name_visible_property_diff.value.previous is None
#     name_protected_property_diff = name_attribute_diff.properties["IS_PROTECTED"]
#     assert name_protected_property_diff.branch == branch.name
#     assert name_protected_property_diff.type == "IS_PROTECTED"
#     assert name_protected_property_diff.action == DiffAction.ADDED
#     assert name_protected_property_diff.path == f"data/{new_person.id}/name/property/IS_PROTECTED"
#     assert name_protected_property_diff.value.new is False
#     assert name_protected_property_diff.value.previous is None
#     height_attribute_diff = node_diff_element.attributes["height"]
#     assert height_attribute_diff.name == "height"
#     assert height_attribute_diff.path == f"data/{new_person.id}/height"
#     assert height_attribute_diff.action == DiffAction.ADDED
#     assert len(height_attribute_diff.properties) == 3
#     assert set(height_attribute_diff.properties.keys()) == {"HAS_VALUE", "IS_PROTECTED", "IS_VISIBLE"}
#     height_value_property_diff = height_attribute_diff.properties["HAS_VALUE"]
#     assert height_value_property_diff.branch == branch.name
#     assert height_value_property_diff.type == "HAS_VALUE"
#     assert height_value_property_diff.action == DiffAction.ADDED
#     assert height_value_property_diff.path == f"data/{new_person.id}/height/value"
#     assert height_value_property_diff.value.new == "NULL"
#     assert height_value_property_diff.value.previous is None
#     height_visible_property_diff = height_attribute_diff.properties["IS_VISIBLE"]
#     assert height_visible_property_diff.branch == branch.name
#     assert height_visible_property_diff.type == "IS_VISIBLE"
#     assert height_visible_property_diff.action == DiffAction.ADDED
#     assert height_visible_property_diff.path == f"data/{new_person.id}/height/property/IS_VISIBLE"
#     assert height_visible_property_diff.value.new is True
#     assert height_visible_property_diff.value.previous is None
#     height_protected_property_diff = height_attribute_diff.properties["IS_PROTECTED"]
#     assert height_protected_property_diff.branch == branch.name
#     assert height_protected_property_diff.type == "IS_PROTECTED"
#     assert height_protected_property_diff.action == DiffAction.ADDED
#     assert height_protected_property_diff.path == f"data/{new_person.id}/height/property/IS_PROTECTED"
#     assert height_protected_property_diff.value.new is False
#     assert height_protected_property_diff.value.previous is None


# async def test_diff_query_index_update_node(
#     db: InfrahubDatabase, person_alfred_main, person_john_main, car_accord_main
# ):
#     branch = await create_branch(db=db, branch_name="branch")
#     alfred_branch = await NodeManager.get_one(db=db, branch=branch, id=person_alfred_main.id)
#     alfred_branch.name.value = "not alfred"
#     await alfred_branch.save(db=db)
#     diff_query = await DiffAllPathsQuery.init(
#         db=db,
#         branch=branch,
#     )

#     breakpoint()

#     await diff_query.execute(db=db)

#     diff_index = DiffQueryParser(diff_query=diff_query)
#     diff_index.parse()
