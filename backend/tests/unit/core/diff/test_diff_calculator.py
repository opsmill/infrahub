from collections import defaultdict
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub import config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, DiffAction, InfrahubKind, RelationshipCardinality, SchemaPathType
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.calculator import DiffCalculator
from infrahub.core.diff.model.field_specifiers_map import NodeFieldSpecifierMap
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.query.relationship_duplicate import RelationshipDuplicateQuery, SchemaRelationshipInfo
from infrahub.core.migrations.schema.attribute_name_update import AttributeNameUpdateMigration
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

if TYPE_CHECKING:
    from infrahub.core.diff.model.path import DiffNode


@pytest.fixture(autouse=True, scope="module")
def low_query_size_limit():
    original = config.SETTINGS.database.query_size_limit
    config.SETTINGS.database.query_size_limit = 30

    yield

    config.SETTINGS.database.query_size_limit = original


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
    assert node_diff.is_node_kind_migration is False
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


async def test_attribute_branch_update_from_null(db: InfrahubDatabase, default_branch: Branch, person_john_main: Node):
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


async def test_attribute_property_branch_create_multiple_updates(
    db: InfrahubDatabase, default_branch: Branch, person_alfred_main, person_john_main, car_accord_main
):
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
    assert set(attributes_by_name.keys()) == {"name", "height"}
    # name attribute
    attribute_diff = attributes_by_name["name"]
    assert attribute_diff.action is DiffAction.ADDED
    prop_diffs_by_type = {p.property_type: p for p in attribute_diff.properties}
    assert set(prop_diffs_by_type.keys()) == {
        DatabaseEdgeType.HAS_VALUE,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.HAS_VALUE, "Gerald Four"),
        (DatabaseEdgeType.IS_VISIBLE, True),
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
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.HAS_VALUE, 160),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        property_diff = prop_diffs_by_type[prop_type]
        assert property_diff.action is DiffAction.ADDED
        assert property_diff.previous_value is None
        assert property_diff.new_value == new_value
        assert from_time < property_diff.changed_at < after_create


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
    assert node_diff.is_node_kind_migration is False
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
    diff_node = branch_root_path.nodes.pop()
    assert diff_node.uuid == new_car.get_id()
    assert diff_node.action is DiffAction.UPDATED
    assert diff_node.is_node_kind_migration is False
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
    assert len(base_root_path.nodes) == 0
    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    node_diff = branch_root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
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
    assert node_diff.is_node_kind_migration is False
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
    assert node_diff.is_node_kind_migration is False
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
    assert node_diff.action is DiffAction.UNCHANGED
    assert node_diff.is_node_kind_migration is False
    assert len(node_diff.relationships) == 0
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UNCHANGED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == person_alfred_main.name.value
    assert property_diff.new_value == person_alfred_main.name.value
    assert property_diff.action is DiffAction.UNCHANGED

    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    node_diff = branch_root_path.nodes[0]
    assert node_diff.uuid == person_alfred_main.id
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
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
    assert set(attributes_by_name.keys()) == {"color"}
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
        DatabaseEdgeType.IS_VISIBLE,
    }
    visible_prop = prop_diff_by_type[DatabaseEdgeType.IS_VISIBLE]
    assert visible_prop.action is DiffAction.UPDATED
    assert visible_prop.new_value is False
    assert visible_prop.previous_value is True
    assert before_main_change < visible_prop.changed_at < after_main_change
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


async def test_node_deleted_on_base_update_on_branch(
    db: InfrahubDatabase, default_branch: Branch, person_alfred_main, person_john_main, car_accord_main
):
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
    # update on branch
    diff_root = calculated_diffs.diff_branch_diff
    assert len(diff_root.nodes) == 1
    diff_node = diff_root.nodes.pop()
    assert diff_node.action is DiffAction.UPDATED
    assert diff_node.uuid == person_alfred_main.id
    assert diff_node.is_node_kind_migration is False
    attributes_by_name = {a.name: a for a in diff_node.attributes}
    assert set(attributes_by_name.keys()) == {"name"}
    attr_diff = diff_node.attributes.pop()
    assert attr_diff.action is DiffAction.UPDATED
    props_by_type = {p.property_type: p for p in attr_diff.properties}
    assert set(props_by_type.keys()) == {DatabaseEdgeType.HAS_VALUE}
    prop_diff = attr_diff.properties.pop()
    assert prop_diff.action is DiffAction.UPDATED
    assert prop_diff.previous_value == "Alfred"
    assert prop_diff.new_value == "Still Alfred"
    assert len(diff_node.relationships) == 0


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


async def test_hierarchy_with_same_kind_parent_and_child(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
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
        DatabaseEdgeType.IS_VISIBLE,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_RELATED, mid_node.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
        (DatabaseEdgeType.IS_VISIBLE, True),
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
        DatabaseEdgeType.IS_VISIBLE,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_RELATED, top_node.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
        (DatabaseEdgeType.IS_VISIBLE, True),
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
        DatabaseEdgeType.IS_VISIBLE,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_RELATED, bottom_node.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
        (DatabaseEdgeType.IS_VISIBLE, True),
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
        DatabaseEdgeType.IS_VISIBLE,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_RELATED, mid_node.id),
        (DatabaseEdgeType.IS_PROTECTED, False),
        (DatabaseEdgeType.IS_VISIBLE, True),
    ):
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.action is DiffAction.ADDED
        assert diff_prop.previous_value is None
        assert diff_prop.new_value == new_value


async def test_diff_unchanged_included_when_not_first_diff(
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
    assert len(node_diff.attributes) == 1
    attribute_diff = node_diff.attributes[0]
    assert attribute_diff.name == "name"
    assert attribute_diff.action is DiffAction.UNCHANGED
    assert len(attribute_diff.properties) == 1
    property_diff = attribute_diff.properties[0]
    assert property_diff.property_type == DatabaseEdgeType.HAS_VALUE
    assert property_diff.previous_value == "Alfred"
    assert property_diff.new_value == "Alfred"
    assert property_diff.action is DiffAction.UNCHANGED

    branch_root_path = calculated_diffs.diff_branch_diff
    assert branch_root_path.branch == branch.name
    assert len(branch_root_path.nodes) == 1
    # person on branch
    node_diff = branch_root_path.nodes[0]
    assert node_diff.kind == "TestPerson"
    assert node_diff.action is DiffAction.UPDATED
    assert node_diff.is_node_kind_migration is False
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


async def test_create_local_and_aware_nodes_on_branch(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_branch_local: SchemaBranch
):
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
    assert set(attrs_by_name.keys()) == {"name", "height"}
    for attr_diff in node_diff.attributes:
        assert attr_diff.action is DiffAction.ADDED


async def test_create_aware_and_agnostic_nodes_on_branch(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_global
):
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
    assert set(attrs_by_name.keys()) == {"name", "color", "is_electric"}
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


async def test_diff_relationship_update_includes_unchanged_properties(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_alfred_main: Node,
    person_john_main: Node,
    car_accord_main: Node,
):
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
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    related_prop = properties_by_type[DatabaseEdgeType.IS_RELATED]
    assert related_prop.action is DiffAction.ADDED
    assert related_prop.previous_value is None
    assert related_prop.new_value == person_alfred_main.id
    for prop_type, value in ((DatabaseEdgeType.IS_VISIBLE, True), (DatabaseEdgeType.IS_PROTECTED, False)):
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
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    related_prop = properties_by_type[DatabaseEdgeType.IS_RELATED]
    assert related_prop.action is DiffAction.REMOVED
    assert related_prop.previous_value == car_accord_main.id
    assert related_prop.new_value is None
    for prop_type, value in ((DatabaseEdgeType.IS_VISIBLE, True), (DatabaseEdgeType.IS_PROTECTED, False)):
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
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    related_prop = properties_by_type[DatabaseEdgeType.IS_RELATED]
    assert related_prop.action is DiffAction.ADDED
    assert related_prop.previous_value is None
    assert related_prop.new_value == car_accord_main.id
    for prop_type, value in ((DatabaseEdgeType.IS_VISIBLE, True), (DatabaseEdgeType.IS_PROTECTED, False)):
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
):
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


async def test_calculate_with_migrated_kind_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main,
    car_camry_main,
    person_john_main,
    person_jane_main,
    person_alfred_main,
    person_albert_main,
):
    """Test that the diff can correctly handle a schema kind migration, which results in 2 nodes with the same UUID"""
    branch = await create_branch(db=db, branch_name="branch-migrated-kind")
    branch_car = await Node.init(db=db, schema="TestCar", branch=branch)
    await branch_car.new(db=db, name="nova", nbr_seats=2, is_electric=False, owner=person_jane_main.id)
    await branch_car.save(db=db)

    # attribute and rel changes before migration
    new_branch_camry_nbr_seats = 9
    new_main_camry_nbr_seats = 7
    new_branch_camry_owner_id = person_albert_main.id
    new_main_camry_owner_id = person_alfred_main.id
    branch_car_camry = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    branch_car_camry.nbr_seats.value = new_branch_camry_nbr_seats
    await branch_car_camry.owner.update(db=db, data=new_branch_camry_owner_id)
    await branch_car_camry.save(db=db)
    main_car_camry = await NodeManager.get_one(db=db, branch=default_branch, id=car_camry_main.id)
    main_car_camry.nbr_seats.value = new_main_camry_nbr_seats
    await main_car_camry.owner.update(db=db, data=new_main_camry_owner_id)
    await main_car_camry.save(db=db)

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    car_schema = schema.get(name="TestCar")
    car_schema.name = "NewCar"
    car_schema.namespace = "Test2"
    assert car_schema.kind == "Test2NewCar"
    registry.schema.set(name="Test2NewCar", schema=car_schema, branch=branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"),
    )
    execution_result = await migration.execute(db=db, branch=branch)
    assert not execution_result.errors

    # attribute and rel changes after migration
    new_branch_camry_color = "#112233"
    new_main_camry_color = "#332211"
    new_branch_camry_driver_id = person_john_main.id
    new_main_camry_driver_id = person_jane_main.id
    migrated_car_camry = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    migrated_car_camry.color.value = new_branch_camry_color
    await migrated_car_camry.driver.update(db=db, data=new_branch_camry_driver_id)
    await migrated_car_camry.save(db=db)
    main_car_camry = await NodeManager.get_one(db=db, branch=default_branch, id=car_camry_main.id)
    main_car_camry.color.value = new_main_camry_color
    await main_car_camry.driver.update(db=db, data=new_main_camry_driver_id)
    await main_car_camry.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    node_specifier_map = NodeFieldSpecifierMap()

    diff_time_1 = Timestamp()
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=Timestamp(branch.get_branched_from()),
        to_time=diff_time_1,
        previous_node_specifiers=node_specifier_map,
        include_unchanged=True,
    )

    base_diff = calculated_diffs.base_branch_diff
    assert len(base_diff.nodes) == 2
    nodes_by_id_and_kind = {(n.uuid, n.kind): n for n in base_diff.nodes}
    assert len(base_diff.nodes) == 2
    assert set(nodes_by_id_and_kind.keys()) == {
        (car_camry_main.id, "TestCar"),
        (person_jane_main.id, person_jane_main.get_kind()),
    }
    # validate the jane has owner relationship removed
    jane_base_diff = nodes_by_id_and_kind[person_jane_main.id, person_jane_main.get_kind()]
    assert jane_base_diff.action is DiffAction.UPDATED
    assert jane_base_diff.is_node_kind_migration is False
    assert not jane_base_diff.attributes
    rels_by_name = {r.name: r for r in jane_base_diff.relationships}
    assert set(rels_by_name.keys()) == {"cars"}
    car_rel_diff = rels_by_name["cars"]
    assert car_rel_diff.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in car_rel_diff.relationships}
    assert set(elements_by_peer_id.keys()) == {car_camry_main.id}
    element_diff = elements_by_peer_id[car_camry_main.id]
    assert element_diff.action is DiffAction.REMOVED
    props_by_type = {p.property_type: p for p in element_diff.properties}
    assert set(props_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, prop_value in [
        (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        prop_diff = props_by_type[prop_type]
        assert prop_diff.action is DiffAction.REMOVED
        assert prop_diff.previous_value == prop_value
        assert prop_diff.new_value is None

    # validate that camry has color, nbr_seats, owner, driver changes on main
    camry_base_diff = nodes_by_id_and_kind[car_camry_main.id, "TestCar"]
    assert camry_base_diff.action is DiffAction.UPDATED
    assert camry_base_diff.is_node_kind_migration is False
    attr_diffs_by_name = {a.name: a for a in camry_base_diff.attributes}
    assert set(attr_diffs_by_name.keys()) == {"nbr_seats", "color"}
    for attr_diff in camry_base_diff.attributes:
        assert attr_diff.action is DiffAction.UPDATED
        props_by_type = {p.property_type: p for p in attr_diff.properties}
        assert set(props_by_type.keys()) == {DatabaseEdgeType.HAS_VALUE}
        prop_diff = attr_diff.properties[0]
        assert prop_diff.action is DiffAction.UPDATED
        if attr_diff.name == "color":
            assert prop_diff.previous_value == car_camry_main.color.value
            assert prop_diff.new_value == new_main_camry_color
        else:
            assert prop_diff.previous_value == car_camry_main.nbr_seats.value
            assert prop_diff.new_value == new_main_camry_nbr_seats
    rel_diffs_by_name = {r.name: r for r in camry_base_diff.relationships}
    assert set(rel_diffs_by_name.keys()) == {"owner", "driver"}
    owner_rel_diff = rel_diffs_by_name["owner"]
    assert owner_rel_diff.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in owner_rel_diff.relationships}
    assert set(elements_by_peer_id) == {person_jane_main.id, person_alfred_main.id}
    jane_element = elements_by_peer_id[person_jane_main.id]
    assert jane_element.action is DiffAction.REMOVED
    props_by_type = {p.property_type: p for p in jane_element.properties}
    assert set(props_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for property_type, previous_prop_value in (
        (DatabaseEdgeType.IS_RELATED, person_jane_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        property_diff = props_by_type[property_type]
        assert property_diff.action is DiffAction.REMOVED
        assert property_diff.previous_value == previous_prop_value
        assert property_diff.new_value is None
    alfred_element = elements_by_peer_id[person_alfred_main.id]
    assert alfred_element.action is DiffAction.ADDED
    props_by_type = {p.property_type: p for p in alfred_element.properties}
    assert set(props_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for property_type, new_prop_value in (
        (DatabaseEdgeType.IS_RELATED, person_alfred_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        property_diff = props_by_type[property_type]
        assert property_diff.action is DiffAction.ADDED
        assert property_diff.previous_value is None
        assert property_diff.new_value == new_prop_value
    driver_rel_diff = rel_diffs_by_name["driver"]
    assert driver_rel_diff.action is DiffAction.ADDED
    elements_by_peer_id = {e.peer_id: e for e in driver_rel_diff.relationships}
    assert set(elements_by_peer_id) == {new_main_camry_driver_id}
    driver_element = elements_by_peer_id[new_main_camry_driver_id]
    assert driver_element.action is DiffAction.ADDED
    props_by_type = {p.property_type: p for p in driver_element.properties}
    assert set(props_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for property_type, new_prop_value in (
        (DatabaseEdgeType.IS_RELATED, new_main_camry_driver_id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        property_diff = props_by_type[property_type]
        assert property_diff.action is DiffAction.ADDED
        assert property_diff.previous_value is None
        assert property_diff.new_value == new_prop_value

    branch_diff = calculated_diffs.diff_branch_diff
    assert len(branch_diff.nodes) == 8
    nodes_by_id_and_kind = {(n.uuid, n.kind): n for n in branch_diff.nodes}
    assert set(nodes_by_id_and_kind.keys()) == {
        (branch_car.id, "Test2NewCar"),
        (person_jane_main.id, person_jane_main.get_kind()),
        (person_albert_main.id, person_albert_main.get_kind()),
        (person_john_main.id, person_john_main.get_kind()),
        (car_accord_main.id, "TestCar"),
        (car_accord_main.id, "Test2NewCar"),
        (car_camry_main.id, "TestCar"),
        (car_camry_main.id, "Test2NewCar"),
    }
    # validate relationship on jane is correct
    jane_diff = nodes_by_id_and_kind[person_jane_main.id, person_jane_main.get_kind()]
    assert jane_diff.action is DiffAction.UPDATED
    assert jane_diff.is_node_kind_migration is False
    assert len(jane_diff.attributes) == 0
    rels_by_name = {r.name: r for r in jane_diff.relationships}
    assert set(rels_by_name.keys()) == {"cars"}
    cars_rel_diff = rels_by_name["cars"]
    assert cars_rel_diff.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in cars_rel_diff.relationships}
    assert set(elements_by_peer_id) == {branch_car.id, car_camry_main.id}
    branch_car_element_diff = elements_by_peer_id[branch_car.id]
    assert branch_car_element_diff.action is DiffAction.ADDED
    props_by_type = {p.property_type: p for p in branch_car_element_diff.properties}
    for property_type, value in (
        (DatabaseEdgeType.IS_RELATED, branch_car.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        property_diff = props_by_type[property_type]
        assert property_diff.action is DiffAction.ADDED
        assert property_diff.new_value == value
        assert property_diff.previous_value is None
    camry_element_diff = elements_by_peer_id[car_camry_main.id]
    assert camry_element_diff.action is DiffAction.REMOVED
    props_by_type = {p.property_type: p for p in camry_element_diff.properties}
    for property_type, value in (
        (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        property_diff = props_by_type[property_type]
        assert property_diff.action is DiffAction.REMOVED
        assert property_diff.new_value is None
        assert property_diff.previous_value == value

    # validate relationship on albert is correct
    albert_diff = nodes_by_id_and_kind[person_albert_main.id, person_albert_main.get_kind()]
    assert albert_diff.action is DiffAction.UPDATED
    assert albert_diff.is_node_kind_migration is False
    assert not albert_diff.attributes
    rel_diffs_by_name = {r.name: r for r in albert_diff.relationships}
    assert set(rel_diffs_by_name.keys()) == {"cars"}
    car_rel_diff = rel_diffs_by_name["cars"]
    assert car_rel_diff.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in car_rel_diff.relationships}
    assert set(elements_by_peer_id.keys()) == {car_camry_main.id}
    camry_element_diff = elements_by_peer_id[car_camry_main.id]
    assert camry_element_diff.action is DiffAction.ADDED
    props_by_type = {p.property_type: p for p in camry_element_diff.properties}
    for property_type, value in (
        (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        property_diff = props_by_type[property_type]
        assert property_diff.action is DiffAction.ADDED
        assert property_diff.new_value == value
        assert property_diff.previous_value is None

    # validate relationship on john is correct
    john_diff = nodes_by_id_and_kind[person_john_main.id, person_john_main.get_kind()]
    assert john_diff.action is DiffAction.UPDATED
    assert john_diff.is_node_kind_migration is False
    assert not john_diff.attributes
    rel_diffs_by_name = {r.name: r for r in john_diff.relationships}
    assert set(rel_diffs_by_name.keys()) == {"cars_driven"}
    car_rel_diff = rel_diffs_by_name["cars_driven"]
    assert car_rel_diff.action is DiffAction.UPDATED
    elements_by_peer_id = {e.peer_id: e for e in car_rel_diff.relationships}
    assert set(elements_by_peer_id.keys()) == {car_camry_main.id}
    camry_element_diff = elements_by_peer_id[car_camry_main.id]
    assert camry_element_diff.action is DiffAction.ADDED
    props_by_type = {p.property_type: p for p in camry_element_diff.properties}
    for property_type, value in (
        (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ):
        property_diff = props_by_type[property_type]
        assert property_diff.action is DiffAction.ADDED
        assert property_diff.new_value == value
        assert property_diff.previous_value is None

    # test new car that was migrated on the branch
    branch_car_diff = nodes_by_id_and_kind[branch_car.id, "Test2NewCar"]
    assert branch_car_diff.action is DiffAction.ADDED
    assert branch_car_diff.is_node_kind_migration is True
    attr_diffs_by_name = {a.name: a for a in branch_car_diff.attributes}
    assert set(attr_diffs_by_name) == {"name", "nbr_seats", "is_electric", "color", "transmission"}
    for attr_name, expected_value in [
        ("name", "nova"),
        ("nbr_seats", 2),
        ("is_electric", False),
        ("color", "#444444"),
        ("transmission", "NULL"),
    ]:
        attr_diff = attr_diffs_by_name[attr_name]
        assert attr_diff.action is DiffAction.ADDED
        props_by_type = {p.property_type: p for p in attr_diff.properties}
        assert set(props_by_type.keys()) == {
            DatabaseEdgeType.HAS_VALUE,
            DatabaseEdgeType.IS_VISIBLE,
            DatabaseEdgeType.IS_PROTECTED,
        }
        for prop_type, prop_value in [
            (DatabaseEdgeType.HAS_VALUE, expected_value),
            (DatabaseEdgeType.IS_VISIBLE, True),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ]:
            prop_diff = props_by_type[prop_type]
            assert prop_diff.action is DiffAction.ADDED
            assert prop_diff.previous_value is None
            assert prop_diff.new_value == prop_value
    rel_diffs_by_name = {r.name: r for r in branch_car_diff.relationships}
    assert set(rel_diffs_by_name.keys()) == {"owner"}
    rel_diff = rel_diffs_by_name["owner"]
    assert rel_diff.action is DiffAction.ADDED
    elements_by_peer_id = {e.peer_id: e for e in rel_diff.relationships}
    assert set(elements_by_peer_id.keys()) == {person_jane_main.id}
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

    # check that old version of migrated node is removed
    old_camry_diff = nodes_by_id_and_kind[car_camry_main.id, "TestCar"]
    assert old_camry_diff.action is DiffAction.REMOVED
    assert old_camry_diff.is_node_kind_migration is True
    assert not old_camry_diff.attributes
    rel_diffs_by_name = {r.name: r for r in old_camry_diff.relationships}
    assert set(rel_diffs_by_name.keys()) == {"owner"}
    rel_diff = rel_diffs_by_name["owner"]
    assert rel_diff.action is DiffAction.REMOVED
    elements_by_peer_id = {e.peer_id: e for e in rel_diff.relationships}
    assert set(elements_by_peer_id.keys()) == {person_jane_main.id}
    jane_element = rel_diff.relationships[0]
    properties_by_type = {p.property_type: p for p in jane_element.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_PROTECTED,
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
    }
    for prop_type, previous_value in (
        (DatabaseEdgeType.IS_PROTECTED, False),
        (DatabaseEdgeType.IS_RELATED, person_jane_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
    ):
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.action is DiffAction.REMOVED
        assert diff_prop.previous_value == previous_value
        assert diff_prop.new_value is None

    # validate new camry that was updated on branch before migration
    new_camry_diff = nodes_by_id_and_kind[car_camry_main.id, "Test2NewCar"]
    assert new_camry_diff.action is DiffAction.ADDED
    assert new_camry_diff.is_node_kind_migration is True
    attr_diffs_by_name = {a.name: a for a in new_camry_diff.attributes}
    assert set(attr_diffs_by_name) == {"nbr_seats", "color"}
    for attr_diff in new_camry_diff.attributes:
        assert attr_diff.action is DiffAction.ADDED
        props_by_type = {p.property_type: p for p in attr_diff.properties}
        assert set(props_by_type.keys()) == {DatabaseEdgeType.HAS_VALUE}
        value_diff_prop = props_by_type[DatabaseEdgeType.HAS_VALUE]
        assert value_diff_prop.action is DiffAction.UPDATED
        if attr_diff.name == "color":
            assert value_diff_prop.previous_value == car_camry_main.color.value
            assert value_diff_prop.new_value == new_branch_camry_color
        elif attr_diff.name == "nbr_seats":
            assert value_diff_prop.previous_value == car_camry_main.nbr_seats.value
            assert value_diff_prop.new_value == new_branch_camry_nbr_seats
    rel_diffs_by_name = {r.name: r for r in new_camry_diff.relationships}
    assert set(rel_diffs_by_name.keys()) == {"owner", "driver"}
    owner_rel_diff = rel_diffs_by_name["owner"]
    assert owner_rel_diff.action is DiffAction.ADDED
    elements_by_peer_id = {e.peer_id: e for e in owner_rel_diff.relationships}
    # only the added owner is included b/c the previous owner has never been a relationship on the migrated node
    assert set(elements_by_peer_id.keys()) == {new_branch_camry_owner_id}
    new_owner_element_diff = owner_rel_diff.relationships[0]
    assert new_owner_element_diff.action is DiffAction.ADDED
    properties_by_type = {p.property_type: p for p in new_owner_element_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_PROTECTED,
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_PROTECTED, False),
        (DatabaseEdgeType.IS_RELATED, new_branch_camry_owner_id),
        (DatabaseEdgeType.IS_VISIBLE, True),
    ):
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.action is DiffAction.ADDED
        assert diff_prop.previous_value is None
        assert diff_prop.new_value == new_value
    new_driver_rel_diff = rel_diffs_by_name["driver"]
    assert new_driver_rel_diff.action is DiffAction.ADDED
    elements_by_peer_id = {e.peer_id: e for e in new_driver_rel_diff.relationships}
    assert set(elements_by_peer_id.keys()) == {new_branch_camry_driver_id}
    new_driver_element_diff = new_driver_rel_diff.relationships[0]
    assert new_driver_element_diff.action is DiffAction.ADDED
    properties_by_type = {p.property_type: p for p in new_driver_element_diff.properties}
    assert set(properties_by_type.keys()) == {
        DatabaseEdgeType.IS_PROTECTED,
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
    }
    for prop_type, new_value in (
        (DatabaseEdgeType.IS_PROTECTED, False),
        (DatabaseEdgeType.IS_RELATED, new_branch_camry_driver_id),
        (DatabaseEdgeType.IS_VISIBLE, True),
    ):
        diff_prop = properties_by_type[prop_type]
        assert diff_prop.action is DiffAction.ADDED
        assert diff_prop.previous_value is None
        assert diff_prop.new_value == new_value

    # validate unchanged migrated node is correct
    old_accord_diff = nodes_by_id_and_kind[car_accord_main.id, "TestCar"]
    new_accord_diff = nodes_by_id_and_kind[car_accord_main.id, "Test2NewCar"]
    for car_diff, expected_action in (
        (old_accord_diff, DiffAction.REMOVED),
        (new_accord_diff, DiffAction.ADDED),
    ):
        assert car_diff.action is expected_action
        assert car_diff.is_node_kind_migration is True
        assert not car_diff.attributes
        assert not car_diff.relationships

    # update attributes and relationship after migration and first diff calculated
    final_branch_camry_name = "ultra camry"
    final_branch_camry_color = "#445566"
    final_branch_camry_owner_id = person_alfred_main.id
    final_main_camry_name = "main ultra camry"
    final_main_camry_color = "#665544"
    final_main_camry_owner_id = person_albert_main.id
    migrated_branch_camry = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    migrated_branch_camry.name.value = final_branch_camry_name
    migrated_branch_camry.color.value = final_branch_camry_color
    await migrated_branch_camry.owner.update(db=db, data=final_branch_camry_owner_id)
    await migrated_branch_camry.save(db=db)
    main_camry = await NodeManager.get_one(db=db, branch=default_branch, id=car_camry_main.id)
    main_camry.name.value = final_main_camry_name
    main_camry.color.value = final_main_camry_color
    await main_camry.owner.update(db=db, data=final_main_camry_owner_id)
    await main_camry.save(db=db)

    # calculate the diff again after these updates
    owner_rel_schema = main_camry.get_schema().get_relationship("owner")
    node_specifier_map = NodeFieldSpecifierMap()
    for field_name in ["color", "name", owner_rel_schema.get_identifier()]:
        node_specifier_map.add_entry(
            node_uuid=car_camry_main.id, kind=migrated_branch_camry.get_kind(), field_name=field_name
        )
        node_specifier_map.add_entry(node_uuid=car_camry_main.id, kind=car_camry_main.get_kind(), field_name=field_name)
    for owner_id in [final_main_camry_owner_id, final_branch_camry_owner_id]:
        node_specifier_map.add_entry(
            node_uuid=owner_id, kind="TestPerson", field_name=owner_rel_schema.get_identifier()
        )

    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=diff_time_1,
        to_time=Timestamp(),
        previous_node_specifiers=node_specifier_map,
        include_unchanged=False,
    )

    # check post-migration update on main correctly captured
    # check attrs and rels on updated, migrated car
    base_diff = calculated_diffs.base_branch_diff
    assert len(base_diff.nodes) == 3
    nodes_by_id_and_kind = {(n.uuid, n.kind): n for n in base_diff.nodes}
    assert set(nodes_by_id_and_kind.keys()) == {
        (car_camry_main.id, car_camry_main.get_kind()),
        (final_main_camry_owner_id, "TestPerson"),
        (new_main_camry_owner_id, "TestPerson"),
    }
    main_camry_diff = nodes_by_id_and_kind[car_camry_main.id, car_camry_main.get_kind()]
    assert main_camry_diff.action is DiffAction.UPDATED
    assert main_camry_diff.is_node_kind_migration is False
    attr_diffs_by_name = {a.name: a for a in main_camry_diff.attributes}
    assert set(attr_diffs_by_name.keys()) == {"color", "name"}
    for attr_name, new_value, previous_value in (
        ("color", final_main_camry_color, car_camry_main.color.value),
        ("name", final_main_camry_name, car_camry_main.name.value),
    ):
        attr_diff = attr_diffs_by_name[attr_name]
        assert attr_diff.action is DiffAction.UPDATED
        props_by_type = {p.property_type: p for p in attr_diff.properties}
        assert set(props_by_type.keys()) == {DatabaseEdgeType.HAS_VALUE}
        prop_diff = attr_diff.properties[0]
        assert prop_diff.action is DiffAction.UPDATED
        assert prop_diff.previous_value == previous_value
        assert prop_diff.new_value == new_value
    rel_diffs_by_name = {r.name: r for r in main_camry_diff.relationships}
    assert set(rel_diffs_by_name.keys()) == {"owner"}
    owner_rel_diff = rel_diffs_by_name["owner"]
    assert owner_rel_diff.action is DiffAction.UPDATED
    peer_id_and_action = {(e.peer_id, e.action) for e in owner_rel_diff.relationships}
    assert peer_id_and_action == {
        (new_main_camry_owner_id, DiffAction.REMOVED),
        (final_main_camry_owner_id, DiffAction.ADDED),
    }

    # check rel on new migrated car owner
    new_owner_diff = nodes_by_id_and_kind[final_main_camry_owner_id, "TestPerson"]
    assert new_owner_diff.is_node_kind_migration is False
    assert new_owner_diff.action is DiffAction.UPDATED
    assert not new_owner_diff.attributes
    rel_diffs_by_name = {r.name: r for r in new_owner_diff.relationships}
    assert set(rel_diffs_by_name.keys()) == {"cars"}
    cars_rel_diff = rel_diffs_by_name["cars"]
    assert cars_rel_diff.action is DiffAction.UPDATED
    peer_id_and_action = {(e.peer_id, e.action) for e in cars_rel_diff.relationships}
    assert peer_id_and_action == {(car_camry_main.id, DiffAction.ADDED)}

    # check rel on previous migrated car owner
    previous_owner_diff = nodes_by_id_and_kind[new_main_camry_owner_id, "TestPerson"]
    assert previous_owner_diff.action is DiffAction.UPDATED
    assert previous_owner_diff.is_node_kind_migration is False
    assert not previous_owner_diff.attributes
    rel_diffs_by_name = {r.name: r for r in previous_owner_diff.relationships}
    assert set(rel_diffs_by_name.keys()) == {"cars"}
    cars_rel_diff = rel_diffs_by_name["cars"]
    assert cars_rel_diff.action is DiffAction.UPDATED
    peer_id_and_action = {(e.peer_id, e.action) for e in cars_rel_diff.relationships}
    assert peer_id_and_action == {(car_camry_main.id, DiffAction.REMOVED)}

    # check post-migration update on branch correctly captured
    branch_diff = calculated_diffs.diff_branch_diff
    assert len(branch_diff.nodes) == 3
    nodes_by_id_and_kind = {(n.uuid, n.kind): n for n in branch_diff.nodes}
    assert set(nodes_by_id_and_kind.keys()) == {
        (car_camry_main.id, migrated_branch_camry.get_kind()),
        (final_branch_camry_owner_id, "TestPerson"),
        (new_branch_camry_owner_id, "TestPerson"),
    }
    branch_camry_diff = nodes_by_id_and_kind[car_camry_main.id, migrated_branch_camry.get_kind()]
    assert branch_camry_diff.action is DiffAction.UPDATED
    assert branch_camry_diff.is_node_kind_migration is False
    attr_diffs_by_name = {a.name: a for a in branch_camry_diff.attributes}
    assert set(attr_diffs_by_name.keys()) == {"color", "name"}
    for attr_name, new_value, previous_value in (
        ("color", final_branch_camry_color, car_camry_main.color.value),
        ("name", final_branch_camry_name, car_camry_main.name.value),
    ):
        attr_diff = attr_diffs_by_name[attr_name]
        assert attr_diff.action is DiffAction.UPDATED
        props_by_type = {p.property_type: p for p in attr_diff.properties}
        assert set(props_by_type.keys()) == {DatabaseEdgeType.HAS_VALUE}
        prop_diff = attr_diff.properties[0]
        assert prop_diff.action is DiffAction.UPDATED
        assert prop_diff.previous_value == previous_value
        assert prop_diff.new_value == new_value
    rel_diffs_by_name = {r.name: r for r in branch_camry_diff.relationships}
    assert set(rel_diffs_by_name.keys()) == {"owner"}
    owner_rel_diff = rel_diffs_by_name["owner"]
    assert owner_rel_diff.action is DiffAction.UPDATED
    peer_id_and_action = {(e.peer_id, e.action) for e in owner_rel_diff.relationships}
    assert peer_id_and_action == {
        (new_branch_camry_owner_id, DiffAction.REMOVED),
        (final_branch_camry_owner_id, DiffAction.ADDED),
    }

    # check rel on new migrated car owner
    new_owner_diff = nodes_by_id_and_kind[final_branch_camry_owner_id, "TestPerson"]
    assert new_owner_diff.action is DiffAction.UPDATED
    assert new_owner_diff.is_node_kind_migration is False
    assert not new_owner_diff.attributes
    rel_diffs_by_name = {r.name: r for r in new_owner_diff.relationships}
    assert set(rel_diffs_by_name.keys()) == {"cars"}
    cars_rel_diff = rel_diffs_by_name["cars"]
    assert cars_rel_diff.action is DiffAction.UPDATED
    peer_id_and_action = {(e.peer_id, e.action) for e in cars_rel_diff.relationships}
    assert peer_id_and_action == {(car_camry_main.id, DiffAction.ADDED)}

    # check rel on previous migrated car owner
    previous_owner_diff = nodes_by_id_and_kind[new_branch_camry_owner_id, "TestPerson"]
    assert previous_owner_diff.action is DiffAction.UPDATED
    assert previous_owner_diff.is_node_kind_migration is False
    assert not previous_owner_diff.attributes
    rel_diffs_by_name = {r.name: r for r in previous_owner_diff.relationships}
    assert set(rel_diffs_by_name.keys()) == {"cars"}
    cars_rel_diff = rel_diffs_by_name["cars"]
    assert cars_rel_diff.action is DiffAction.UPDATED
    peer_id_and_action = {(e.peer_id, e.action) for e in cars_rel_diff.relationships}
    assert peer_id_and_action == {(car_camry_main.id, DiffAction.REMOVED)}


async def test_calculate_with_migrated_attr_name(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main, person_john_main, person_jane_main
):
    """Test that the diff can correctly handle an attribute name migration"""
    branch = await create_branch(db=db, branch_name="branch")
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="color")
    prev_attr.id = str(uuid4())
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="color")
    new_attr.name = "new-color"
    new_attr.id = prev_attr.id
    registry.schema.set(name=new_car_schema.kind, schema=new_car_schema, branch=branch.name)

    migration = AttributeNameUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="new-color"),
    )

    execution_result = await migration.execute(db=db, branch=branch)
    assert not execution_result.errors

    diff_calculator = DiffCalculator(db=db)

    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=Timestamp(branch.get_branched_from()),
        to_time=Timestamp(),
        previous_node_specifiers=None,
        include_unchanged=True,
    )

    branch_diff = calculated_diffs.diff_branch_diff
    assert len(branch_diff.nodes) == 2
    nodes_by_id = {n.uuid: n for n in branch_diff.nodes}
    assert set(nodes_by_id.keys()) == {car_accord_main.id, car_camry_main.id}
    for diff_node in branch_diff.nodes:
        assert diff_node.action is DiffAction.UPDATED
        assert len(diff_node.relationships) == 0
        attrs_by_name = {a.name: a for a in diff_node.attributes}
        assert set(attrs_by_name.keys()) == {"color", "new-color"}
        old_attr_diff = attrs_by_name["color"]
        assert old_attr_diff.action is DiffAction.REMOVED
        props_by_type = {p.property_type: p for p in old_attr_diff.properties}
        assert set(props_by_type.keys()) == {
            DatabaseEdgeType.HAS_VALUE,
            DatabaseEdgeType.IS_VISIBLE,
            DatabaseEdgeType.IS_PROTECTED,
        }
        for property_type, value in (
            (DatabaseEdgeType.HAS_VALUE, car_accord_main.color.value),
            (DatabaseEdgeType.IS_VISIBLE, True),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ):
            diff_prop = props_by_type[property_type]
            assert diff_prop.action is DiffAction.REMOVED
            assert diff_prop.new_value is None
            assert diff_prop.previous_value == value

        new_attr_diff = attrs_by_name["new-color"]
        assert new_attr_diff.action is DiffAction.ADDED
        props_by_type = {p.property_type: p for p in new_attr_diff.properties}
        assert set(props_by_type.keys()) == {
            DatabaseEdgeType.HAS_VALUE,
            DatabaseEdgeType.IS_VISIBLE,
            DatabaseEdgeType.IS_PROTECTED,
        }
        for property_type, value in (
            (DatabaseEdgeType.HAS_VALUE, car_accord_main.color.value),
            (DatabaseEdgeType.IS_VISIBLE, True),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ):
            diff_prop = props_by_type[property_type]
            assert diff_prop.action is DiffAction.ADDED
            assert diff_prop.new_value == value
            assert diff_prop.previous_value is None

    base_diff = calculated_diffs.base_branch_diff
    assert len(base_diff.nodes) == 0


async def test_calculate_with_renamed_relationships(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main, person_john_main, person_jane_main
):
    """Test that the diff can correctly handle an attribute name migration"""
    branch = await create_branch(db=db, branch_name="branch")
    new_rel_identifier = "brand_new_identifier"
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_owner_rel = new_car_schema.get_relationship(name="owner")
    previous_rel_identifier = new_owner_rel.identifier
    new_owner_rel.identifier = new_rel_identifier
    new_person_schema = candidate_schema.get(name="TestPerson")
    new_cars_rel = new_person_schema.get_relationship(name="cars")
    new_cars_rel.identifier = new_rel_identifier
    registry.schema.set(name=new_car_schema.kind, schema=new_car_schema, branch=branch.name)
    registry.schema.set(name=new_person_schema.kind, schema=new_person_schema, branch=branch.name)

    migration_query = await RelationshipDuplicateQuery.init(
        db=db,
        branch=branch,
        previous_rel=SchemaRelationshipInfo(
            name=previous_rel_identifier,
            branch_support=BranchSupportType.AWARE.value,
            src_peer="TestCar",
            dst_peer="TestPerson",
        ),
        new_rel=SchemaRelationshipInfo(
            name=new_rel_identifier,
            branch_support=BranchSupportType.AWARE.value,
            src_peer="TestCar",
            dst_peer="TestPerson",
        ),
    )
    await migration_query.execute(db=db)

    diff_calculator = DiffCalculator(db=db)

    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=Timestamp(branch.get_branched_from()),
        to_time=Timestamp(),
        previous_node_specifiers=None,
        include_unchanged=True,
    )

    branch_diff = calculated_diffs.diff_branch_diff
    assert len(branch_diff.nodes) == 4
    nodes_by_id = {n.uuid: n for n in branch_diff.nodes}
    assert set(nodes_by_id.keys()) == {car_accord_main.id, car_camry_main.id, person_jane_main.id, person_john_main.id}
    for car_id, peer_id in ((car_accord_main.id, person_john_main.id), (car_camry_main.id, person_jane_main.id)):
        car_diff = nodes_by_id[car_id]
        assert car_diff.action is DiffAction.UPDATED
        assert car_diff.is_node_kind_migration is False
        assert len(car_diff.attributes) == 0
        rels_by_identifier = {r.identifier: r for r in car_diff.relationships}
        assert set(rels_by_identifier.keys()) == {previous_rel_identifier, new_rel_identifier}
        # validate removed relationship
        removed_rel = rels_by_identifier[previous_rel_identifier]
        assert removed_rel.name == "owner"
        assert removed_rel.action is DiffAction.REMOVED
        elements_by_peer_id = {e.peer_id: e for e in removed_rel.relationships}
        assert set(elements_by_peer_id.keys()) == {peer_id}
        element_diff = elements_by_peer_id[peer_id]
        assert element_diff.action is DiffAction.REMOVED
        props_by_type = {p.property_type: p for p in element_diff.properties}
        assert set(props_by_type.keys()) == {
            DatabaseEdgeType.IS_RELATED,
            DatabaseEdgeType.IS_VISIBLE,
            DatabaseEdgeType.IS_PROTECTED,
        }
        for property_type, value in (
            (DatabaseEdgeType.IS_RELATED, peer_id),
            (DatabaseEdgeType.IS_VISIBLE, True),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ):
            diff_prop = props_by_type[property_type]
            assert diff_prop.action is DiffAction.REMOVED
            assert diff_prop.new_value is None
            assert diff_prop.previous_value == value
        # validate added relationship
        added_rel = rels_by_identifier[new_rel_identifier]
        assert added_rel.name == "owner"
        assert added_rel.action is DiffAction.ADDED
        elements_by_peer_id = {e.peer_id: e for e in added_rel.relationships}
        assert set(elements_by_peer_id.keys()) == {peer_id}
        element_diff = elements_by_peer_id[peer_id]
        assert element_diff.action is DiffAction.ADDED
        props_by_type = {p.property_type: p for p in element_diff.properties}
        assert set(props_by_type.keys()) == {
            DatabaseEdgeType.IS_RELATED,
            DatabaseEdgeType.IS_VISIBLE,
            DatabaseEdgeType.IS_PROTECTED,
        }
        for property_type, value in (
            (DatabaseEdgeType.IS_RELATED, peer_id),
            (DatabaseEdgeType.IS_VISIBLE, True),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ):
            diff_prop = props_by_type[property_type]
            assert diff_prop.action is DiffAction.ADDED
            assert diff_prop.new_value == value
            assert diff_prop.previous_value is None

    for person_id, peer_id in ((person_john_main.id, car_accord_main.id), (person_jane_main.id, car_camry_main.id)):
        person_diff = nodes_by_id[person_id]
        assert person_diff.action is DiffAction.UPDATED
        assert person_diff.is_node_kind_migration is False
        assert len(person_diff.attributes) == 0
        rels_by_identifier = {r.identifier: r for r in person_diff.relationships}
        assert set(rels_by_identifier.keys()) == {previous_rel_identifier, new_rel_identifier}
        # validate removed relationship
        removed_rel = rels_by_identifier[previous_rel_identifier]
        assert removed_rel.name == "cars"
        assert removed_rel.action is DiffAction.UPDATED
        elements_by_peer_id = {e.peer_id: e for e in removed_rel.relationships}
        assert set(elements_by_peer_id.keys()) == {peer_id}
        element_diff = elements_by_peer_id[peer_id]
        assert element_diff.action is DiffAction.REMOVED
        props_by_type = {p.property_type: p for p in element_diff.properties}
        assert set(props_by_type.keys()) == {
            DatabaseEdgeType.IS_RELATED,
            DatabaseEdgeType.IS_VISIBLE,
            DatabaseEdgeType.IS_PROTECTED,
        }
        for property_type, value in (
            (DatabaseEdgeType.IS_RELATED, peer_id),
            (DatabaseEdgeType.IS_VISIBLE, True),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ):
            diff_prop = props_by_type[property_type]
            assert diff_prop.action is DiffAction.REMOVED
            assert diff_prop.new_value is None
            assert diff_prop.previous_value == value
        # validate added relationship
        added_rel = rels_by_identifier[new_rel_identifier]
        assert added_rel.name == "cars"
        assert added_rel.action is DiffAction.UPDATED
        elements_by_peer_id = {e.peer_id: e for e in added_rel.relationships}
        assert set(elements_by_peer_id.keys()) == {peer_id}
        element_diff = elements_by_peer_id[peer_id]
        assert element_diff.action is DiffAction.ADDED
        props_by_type = {p.property_type: p for p in element_diff.properties}
        assert set(props_by_type.keys()) == {
            DatabaseEdgeType.IS_RELATED,
            DatabaseEdgeType.IS_VISIBLE,
            DatabaseEdgeType.IS_PROTECTED,
        }
        for property_type, value in (
            (DatabaseEdgeType.IS_RELATED, peer_id),
            (DatabaseEdgeType.IS_VISIBLE, True),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ):
            diff_prop = props_by_type[property_type]
            assert diff_prop.action is DiffAction.ADDED
            assert diff_prop.new_value == value
            assert diff_prop.previous_value is None

    base_diff = calculated_diffs.base_branch_diff
    assert len(base_diff.nodes) == 0


async def test_migrated_kind_node_then_peer_delete(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main,
    car_camry_main,
    person_john_main,
    person_jane_main,
    person_alfred_main,
    person_albert_main,
):
    # migrate TestPerson kind on main
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    original_person_schema = schema_branch.get_node(name="TestPerson")
    person_schema = schema_branch.get_node(name="TestPerson")
    person_schema.inherit_from = ["GenericThing"]
    registry.schema.set(name="TestPerson", schema=person_schema, branch=default_branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=original_person_schema,
        new_node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="inherit_from"),
    )
    execution_result = await migration.execute(db=db, branch=default_branch)
    assert not execution_result.errors

    # migrate TestPerson kind back to original on a different branch
    branch = await create_branch(db=db, branch_name="branch-undo-kind-migrate")
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    registry.schema.set_schema_branch(name=branch.name, schema=schema_branch)
    original_person_schema = schema_branch.get_node(name="TestPerson")
    person_schema = schema_branch.get_node(name="TestPerson")
    person_schema.inherit_from = []
    registry.schema.set(name="TestPerson", schema=person_schema, branch=branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=original_person_schema,
        new_node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="inherit_from"),
    )
    execution_result = await migration.execute(db=db, branch=branch)
    assert not execution_result.errors

    # create a branch and delete a car on the branch
    branch = await create_branch(db=db, branch_name="branch-delete-car")
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    registry.schema.set_schema_branch(name=branch.name, schema=schema_branch)
    branch_accord = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await branch_accord.delete(db=db)

    diff_calculator = DiffCalculator(db=db)

    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=Timestamp(branch.get_branched_from()),
        to_time=Timestamp(),
        previous_node_specifiers=None,
        include_unchanged=True,
    )

    base_diff = calculated_diffs.base_branch_diff
    assert base_diff.nodes == []

    branch_diff = calculated_diffs.diff_branch_diff
    nodes_by_id = {n.uuid: n for n in branch_diff.nodes}
    assert len(branch_diff.nodes) == 2
    assert set(nodes_by_id.keys()) == {person_john_main.id, car_accord_main.id}

    person_node = nodes_by_id[person_john_main.id]
    assert person_node.action is DiffAction.UPDATED
    assert person_node.is_node_kind_migration is False
    assert len(person_node.attributes) == 0
    rels_by_identifier = {r.identifier: r for r in person_node.relationships}
    cars_identifier = person_schema.get_relationship(name="cars").get_identifier()
    assert set(rels_by_identifier.keys()) == {cars_identifier}
    cars_rel = rels_by_identifier[cars_identifier]
    assert cars_rel.action is DiffAction.UPDATED
    elements_by_id = {r.peer_id: r for r in cars_rel.relationships}
    assert set(elements_by_id.keys()) == {car_accord_main.id}
    element_diff = elements_by_id[car_accord_main.id]
    assert element_diff.action is DiffAction.REMOVED

    car_node = nodes_by_id[car_accord_main.id]
    assert car_node.action is DiffAction.REMOVED
    assert car_node.is_node_kind_migration is False


async def test_migrated_kind_with_property_level_changes(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main,
    car_camry_main,
    person_john_main,
    person_jane_main,
    person_alfred_main,
):
    branch = await create_branch(db=db, branch_name="lets-migrate")

    # property-level changes before migration
    branch_john = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
    branch_john.name.value = "John Branch"
    await branch_john.save(db=db)
    branch_accord = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await branch_accord.owner.update(db=db, data={"id": person_john_main.id, "_relation__is_visible": False})
    await branch_accord.save(db=db)

    # migrate TestPerson kind on branch
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    registry.schema.set_schema_branch(name=branch.name, schema=schema_branch)
    original_person_schema = schema_branch.get_node(name="TestPerson")
    person_schema = schema_branch.get_node(name="TestPerson")
    person_schema.inherit_from = ["GenericThing"]
    registry.schema.set(name="TestPerson", schema=person_schema, branch=branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=original_person_schema,
        new_node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="inherit_from"),
    )
    execution_result = await migration.execute(db=db, branch=branch)
    assert not execution_result.errors

    # property-level change after migration
    branch_jane = await NodeManager.get_one(db=db, branch=branch, id=person_jane_main.id)
    branch_jane.name.value = "Jane Branch"
    await branch_jane.save(db=db)
    branch_camry = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    await branch_camry.owner.update(db=db, data={"id": person_jane_main.id, "_relation__is_protected": True})
    await branch_camry.save(db=db)

    diff_calculator = DiffCalculator(db=db)

    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=Timestamp(branch.get_branched_from()),
        to_time=Timestamp(),
        previous_node_specifiers=None,
        include_unchanged=True,
    )

    base_diff = calculated_diffs.base_branch_diff
    assert base_diff.nodes == []

    branch_diff = calculated_diffs.diff_branch_diff
    nodes_by_id: dict[str, list[DiffNode]] = defaultdict(list)
    for node in branch_diff.nodes:
        nodes_by_id[node.uuid].append(node)
    assert len(branch_diff.nodes) == 8
    assert set(nodes_by_id.keys()) == {
        person_john_main.id,
        person_jane_main.id,
        person_alfred_main.id,
        car_accord_main.id,
        car_camry_main.id,
    }

    # validate person_alfred_main migrated
    alfred_previous_diff = [n for n in nodes_by_id[person_alfred_main.id] if n.action is DiffAction.REMOVED][0]
    alfred_new_diff = [n for n in nodes_by_id[person_alfred_main.id] if n.action is DiffAction.ADDED][0]
    assert alfred_previous_diff.is_node_kind_migration is True
    assert alfred_previous_diff.attributes == []
    assert alfred_previous_diff.relationships == []
    assert alfred_new_diff.is_node_kind_migration is True
    assert alfred_new_diff.attributes == []
    assert alfred_new_diff.relationships == []

    # validate person_john_main migrated
    john_previous_diff = [n for n in nodes_by_id[person_john_main.id] if n.action is DiffAction.REMOVED][0]
    john_new_diff = [n for n in nodes_by_id[person_john_main.id] if n.action is DiffAction.ADDED][0]
    assert john_previous_diff.is_node_kind_migration is True
    assert john_previous_diff.attributes == []
    assert john_previous_diff.relationships == []
    assert john_new_diff.is_node_kind_migration is True
    attributes_by_name = {a.name: a for a in john_new_diff.attributes}
    assert set(attributes_by_name.keys()) == {"name"}
    name_attr = attributes_by_name["name"]
    # it would be more correct if this was DiffAction.UPDATED, but ADDED is also technically correct for a node kind migration
    assert name_attr.action is DiffAction.ADDED
    properties_by_type = {p.property_type: p for p in name_attr.properties}
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.HAS_VALUE}
    has_value_prop = properties_by_type[DatabaseEdgeType.HAS_VALUE]
    assert has_value_prop.action is DiffAction.UPDATED
    assert has_value_prop.new_value == "John Branch"
    assert has_value_prop.previous_value == "John"
    relationships_by_identifier = {r.identifier: r for r in john_new_diff.relationships}
    assert set(relationships_by_identifier.keys()) == {"testcar__testperson"}
    cars_rel = relationships_by_identifier["testcar__testperson"]
    assert cars_rel.action is DiffAction.UPDATED
    elements_by_id = {r.peer_id: r for r in cars_rel.relationships}
    assert set(elements_by_id.keys()) == {car_accord_main.id}
    element_diff = elements_by_id[car_accord_main.id]
    assert element_diff.action is DiffAction.UPDATED
    assert element_diff.peer_id == car_accord_main.id
    properties_by_type = {p.property_type: p for p in element_diff.properties if p.action != DiffAction.UNCHANGED}
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_VISIBLE}
    is_visible_prop = properties_by_type[DatabaseEdgeType.IS_VISIBLE]
    assert is_visible_prop.action is DiffAction.UPDATED
    assert is_visible_prop.new_value is False
    assert is_visible_prop.previous_value is True

    # validate person_jane_main migrated
    jane_previous_diff = [n for n in nodes_by_id[person_jane_main.id] if n.action is DiffAction.REMOVED][0]
    jane_new_diff = [n for n in nodes_by_id[person_jane_main.id] if n.action is DiffAction.ADDED][0]
    assert jane_previous_diff.is_node_kind_migration is True
    assert jane_previous_diff.attributes == []
    assert jane_previous_diff.relationships == []
    assert jane_new_diff.is_node_kind_migration is True
    attributes_by_name = {a.name: a for a in jane_new_diff.attributes}
    assert set(attributes_by_name.keys()) == {"name"}
    name_attr = attributes_by_name["name"]
    # it would be more correct if this was DiffAction.UPDATED, but ADDED is also technically correct for a node kind migration
    assert name_attr.action is DiffAction.ADDED
    properties_by_type = {p.property_type: p for p in name_attr.properties}
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.HAS_VALUE}
    has_value_prop = properties_by_type[DatabaseEdgeType.HAS_VALUE]
    assert has_value_prop.action is DiffAction.UPDATED
    assert has_value_prop.new_value == "Jane Branch"
    assert has_value_prop.previous_value == "Jane"
    relationships_by_identifier = {r.identifier: r for r in jane_new_diff.relationships}
    assert set(relationships_by_identifier.keys()) == {"testcar__testperson"}
    cars_rel = relationships_by_identifier["testcar__testperson"]
    assert cars_rel.action is DiffAction.UPDATED
    elements_by_id = {r.peer_id: r for r in cars_rel.relationships}
    assert set(elements_by_id.keys()) == {car_camry_main.id}
    element_diff = elements_by_id[car_camry_main.id]
    assert element_diff.action is DiffAction.UPDATED
    assert element_diff.peer_id == car_camry_main.id
    properties_by_type = {p.property_type: p for p in element_diff.properties if p.action != DiffAction.UNCHANGED}
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_PROTECTED}
    is_protected_prop = properties_by_type[DatabaseEdgeType.IS_PROTECTED]
    assert is_protected_prop.action is DiffAction.UPDATED
    assert is_protected_prop.new_value is True
    assert is_protected_prop.previous_value is False

    # validate car_accord
    car_diffs = nodes_by_id[car_accord_main.id]
    assert len(car_diffs) == 1
    car_diff = car_diffs[0]
    assert car_diff.action is DiffAction.UPDATED
    assert car_diff.is_node_kind_migration is False
    assert car_diff.attributes == []
    rels_by_identifier = {r.identifier: r for r in car_diff.relationships}
    assert set(rels_by_identifier.keys()) == {"testcar__testperson"}
    person_rel = rels_by_identifier["testcar__testperson"]
    assert person_rel.action is DiffAction.UPDATED
    elements_by_id = {r.peer_id: r for r in person_rel.relationships}
    assert set(elements_by_id.keys()) == {person_john_main.id}
    element_diff = elements_by_id[person_john_main.id]
    assert element_diff.action is DiffAction.UPDATED
    assert element_diff.peer_id == person_john_main.id
    properties_by_type = {p.property_type: p for p in element_diff.properties if p.action != DiffAction.UNCHANGED}
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_VISIBLE}
    is_visible_prop = properties_by_type[DatabaseEdgeType.IS_VISIBLE]
    assert is_visible_prop.action is DiffAction.UPDATED
    assert is_visible_prop.new_value is False
    assert is_visible_prop.previous_value is True

    # validate car_camry
    car_diffs = nodes_by_id[car_camry_main.id]
    assert len(car_diffs) == 1
    car_diff = car_diffs[0]
    assert car_diff.action is DiffAction.UPDATED
    assert car_diff.is_node_kind_migration is False
    assert car_diff.attributes == []
    rels_by_identifier = {r.identifier: r for r in car_diff.relationships}
    assert set(rels_by_identifier.keys()) == {"testcar__testperson"}
    person_rel = rels_by_identifier["testcar__testperson"]
    assert person_rel.action is DiffAction.UPDATED
    elements_by_id = {r.peer_id: r for r in person_rel.relationships}
    assert set(elements_by_id.keys()) == {person_jane_main.id}
    element_diff = elements_by_id[person_jane_main.id]
    assert element_diff.action is DiffAction.UPDATED
    assert element_diff.peer_id == person_jane_main.id
    properties_by_type = {p.property_type: p for p in element_diff.properties if p.action != DiffAction.UNCHANGED}
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_PROTECTED}
    is_protected_prop = properties_by_type[DatabaseEdgeType.IS_PROTECTED]
    assert is_protected_prop.action is DiffAction.UPDATED
    assert is_protected_prop.new_value is True
    assert is_protected_prop.previous_value is False


async def test_migrated_kind_on_main_then_relationship_update_on_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main,
    car_camry_main,
    person_john_main,
    person_jane_main,
    person_alfred_main,
    person_albert_main,
):
    """Test that when a schema kind is migrated on the default branch, relationships to instances
    of the migrated node can be updated on a branch before the diff is calculated."""
    # Migrate TestPerson kind on default branch
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    original_person_schema = schema_branch.get_node(name="TestPerson")
    person_schema = schema_branch.get_node(name="TestPerson")
    person_schema.inherit_from = ["GenericThing"]
    registry.schema.set(name="TestPerson", schema=person_schema, branch=default_branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=original_person_schema,
        new_node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="inherit_from"),
    )
    execution_result = await migration.execute(db=db, branch=default_branch)
    assert not execution_result.errors

    # Create a branch after the migration
    branch = await create_branch(db=db, branch_name="branch-with-relationship-updates")

    # Update relationships on the branch that reference instances of the migrated node
    branch_accord = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await branch_accord.owner.update(db=db, data=person_albert_main.id)
    await branch_accord.save(db=db)

    branch_camry = await NodeManager.get_one(db=db, branch=branch, id=car_camry_main.id)
    await branch_camry.owner.update(db=db, data={"id": person_jane_main.id, "_relation__is_protected": True})
    await branch_camry.save(db=db)

    # Calculate the diff
    diff_calculator = DiffCalculator(db=db)

    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=Timestamp(branch.get_branched_from()),
        to_time=Timestamp(),
        previous_node_specifiers=None,
        include_unchanged=True,
    )

    base_diff = calculated_diffs.base_branch_diff
    assert len(base_diff.nodes) == 0

    branch_diff = calculated_diffs.diff_branch_diff
    nodes_by_id: dict[str, list[DiffNode]] = defaultdict(list)
    for node in branch_diff.nodes:
        nodes_by_id[node.uuid].append(node)

    # Verify that the cars and related persons appear in the diff
    expected_ids = {
        car_accord_main.id,
        car_camry_main.id,
        person_john_main.id,
        person_jane_main.id,
        person_albert_main.id,
    }
    assert set(nodes_by_id.keys()) == expected_ids
    assert len(nodes_by_id) == len(expected_ids)

    # Get the car schema to find the owner relationship identifier
    car_schema = registry.schema.get(name="TestCar", branch=branch.name)
    owner_rel_schema = car_schema.get_relationship(name="owner")
    owner_identifier = owner_rel_schema.get_identifier()

    # Validate car_accord relationship update
    accord_diffs = nodes_by_id[car_accord_main.id]
    assert len(accord_diffs) == 1
    accord_diff = accord_diffs[0]
    assert accord_diff.action is DiffAction.UPDATED
    assert accord_diff.is_node_kind_migration is False
    rels_by_identifier = {r.identifier: r for r in accord_diff.relationships}
    assert owner_identifier in rels_by_identifier
    owner_rel_diff = rels_by_identifier[owner_identifier]
    assert owner_rel_diff.action is DiffAction.UPDATED
    elements_by_id = {r.peer_id: r for r in owner_rel_diff.relationships}
    assert set(elements_by_id.keys()) == {person_john_main.id, person_albert_main.id}
    # Original owner was person_john_main, so it should be REMOVED
    john_element = elements_by_id[person_john_main.id]
    assert john_element.action is DiffAction.REMOVED
    # Verify the relationship properties for the removed owner
    props_by_type = {p.property_type: p for p in john_element.properties}
    assert set(props_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_VISIBLE,
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in [
        (DatabaseEdgeType.IS_RELATED, person_john_main.id),
        (DatabaseEdgeType.IS_VISIBLE, True),
        (DatabaseEdgeType.IS_PROTECTED, False),
    ]:
        prop_diff = props_by_type[prop_type]
        assert prop_diff.action is DiffAction.REMOVED
        assert prop_diff.previous_value == previous_value
        assert prop_diff.new_value is None
    # The owner should have been updated to person_albert_main
    albert_element = elements_by_id[person_albert_main.id]
    assert albert_element.action is DiffAction.ADDED
    # Verify the relationship properties for the new owner
    props_by_type = {p.property_type: p for p in albert_element.properties}
    assert DatabaseEdgeType.IS_RELATED in props_by_type
    is_related_prop = props_by_type[DatabaseEdgeType.IS_RELATED]
    assert is_related_prop.action is DiffAction.ADDED
    assert is_related_prop.new_value == person_albert_main.id

    # Validate car_camry relationship update
    camry_diffs = nodes_by_id[car_camry_main.id]
    assert len(camry_diffs) == 1
    camry_diff = camry_diffs[0]
    assert camry_diff.action is DiffAction.UPDATED
    assert camry_diff.is_node_kind_migration is False
    rels_by_identifier = {r.identifier: r for r in camry_diff.relationships}
    assert owner_identifier in rels_by_identifier
    owner_rel_diff = rels_by_identifier[owner_identifier]
    assert owner_rel_diff.action is DiffAction.UPDATED
    elements_by_id = {r.peer_id: r for r in owner_rel_diff.relationships}
    # The owner relationship with person_jane_main should have is_protected updated
    assert set(elements_by_id.keys()) == {person_jane_main.id}
    element_diff = elements_by_id[person_jane_main.id]
    assert element_diff.action is DiffAction.UPDATED
    properties_by_type = {p.property_type: p for p in element_diff.properties if p.action != DiffAction.UNCHANGED}
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_PROTECTED}
    is_protected_prop = properties_by_type[DatabaseEdgeType.IS_PROTECTED]
    assert is_protected_prop.action is DiffAction.UPDATED
    assert is_protected_prop.new_value is True
    assert is_protected_prop.previous_value is False

    # Validate only correct TestPerson nodes are present in the diff
    current_persons_map = await NodeManager.get_many(
        db=db, ids=[person_john_main.id, person_jane_main.id, person_albert_main.id]
    )
    for person_id in [person_john_main.id, person_jane_main.id, person_albert_main.id]:
        person_object = current_persons_map[person_id]
        person_diffs = nodes_by_id[person_id]
        assert len(person_diffs) == 1
        person_diff = person_diffs[0]
        assert person_diff.identifier.db_id == person_object.db_id
        assert person_diff.action is DiffAction.UPDATED
        assert person_diff.is_node_kind_migration is False
        assert person_diff.attributes == []
        assert len(person_diff.relationships) == 1
        rel_diff = person_diff.relationships[0]
        assert rel_diff.name == "cars"
        assert rel_diff.action is DiffAction.UPDATED
