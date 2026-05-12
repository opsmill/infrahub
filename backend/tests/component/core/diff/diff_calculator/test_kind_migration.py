from collections import defaultdict
from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, DiffAction, SchemaPathType
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.calculator import DiffCalculator
from infrahub.core.diff.model.field_specifiers_map import NodeFieldSpecifierMap
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.query.relationship_duplicate import RelationshipDuplicateQuery, SchemaRelationshipInfo
from infrahub.core.migrations.schema.attribute_name_update import AttributeNameUpdateMigration
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

if TYPE_CHECKING:
    from infrahub.core.diff.model.path import DiffNode


def _assert_added_property_diffs(props_by_type: dict, expected: tuple) -> None:
    for prop_type, new_value in expected:
        prop_diff = props_by_type[prop_type]
        assert prop_diff.action is DiffAction.ADDED
        assert prop_diff.previous_value is None
        assert prop_diff.new_value == new_value


def _assert_removed_property_diffs(props_by_type: dict, expected: tuple) -> None:
    for prop_type, previous_value in expected:
        prop_diff = props_by_type[prop_type]
        assert prop_diff.action is DiffAction.REMOVED
        assert prop_diff.previous_value == previous_value
        assert prop_diff.new_value is None


async def test_calculate_with_migrated_kind_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_camry_main: Node,
    person_john_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
    person_albert_main: Node,
) -> None:
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
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
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
        DatabaseEdgeType.IS_PROTECTED,
    }
    _assert_removed_property_diffs(
        props_by_type,
        [
            (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ],
    )

    # validate that camry has color, nbr_seats, owner, driver changes on main
    camry_base_diff = nodes_by_id_and_kind[car_camry_main.id, "TestCar"]
    assert camry_base_diff.action is DiffAction.UPDATED
    assert camry_base_diff.is_node_kind_migration is False
    attr_diffs_by_name = {a.name: a for a in camry_base_diff.attributes}
    assert set(attr_diffs_by_name.keys()) == {"nbr_seats", "color", "display_label"}
    for attr_diff in camry_base_diff.attributes:
        assert attr_diff.action is DiffAction.UPDATED
        props_by_type = {p.property_type: p for p in attr_diff.properties}
        assert set(props_by_type.keys()) == {DatabaseEdgeType.HAS_VALUE}
        prop_diff = attr_diff.properties[0]
        assert prop_diff.action is DiffAction.UPDATED
        if attr_diff.name == "color":
            assert prop_diff.previous_value == car_camry_main.color.value
            assert prop_diff.new_value == new_main_camry_color
        elif attr_diff.name == "nbr_seats":
            assert prop_diff.previous_value == car_camry_main.nbr_seats.value
            assert prop_diff.new_value == new_main_camry_nbr_seats
        else:
            assert prop_diff.previous_value == f"camry {car_camry_main.color.value}"
            assert prop_diff.new_value == f"camry {new_main_camry_color}"

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
        DatabaseEdgeType.IS_PROTECTED,
    }
    _assert_removed_property_diffs(
        props_by_type,
        (
            (DatabaseEdgeType.IS_RELATED, person_jane_main.id),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ),
    )
    alfred_element = elements_by_peer_id[person_alfred_main.id]
    assert alfred_element.action is DiffAction.ADDED
    props_by_type = {p.property_type: p for p in alfred_element.properties}
    assert set(props_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    _assert_added_property_diffs(
        props_by_type,
        (
            (DatabaseEdgeType.IS_RELATED, person_alfred_main.id),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ),
    )
    driver_rel_diff = rel_diffs_by_name["driver"]
    assert driver_rel_diff.action is DiffAction.ADDED
    elements_by_peer_id = {e.peer_id: e for e in driver_rel_diff.relationships}
    assert set(elements_by_peer_id) == {new_main_camry_driver_id}
    driver_element = elements_by_peer_id[new_main_camry_driver_id]
    assert driver_element.action is DiffAction.ADDED
    props_by_type = {p.property_type: p for p in driver_element.properties}
    assert set(props_by_type.keys()) == {
        DatabaseEdgeType.IS_RELATED,
        DatabaseEdgeType.IS_PROTECTED,
    }
    _assert_added_property_diffs(
        props_by_type,
        (
            (DatabaseEdgeType.IS_RELATED, new_main_camry_driver_id),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ),
    )

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
    _assert_added_property_diffs(
        props_by_type,
        (
            (DatabaseEdgeType.IS_RELATED, branch_car.id),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ),
    )
    camry_element_diff = elements_by_peer_id[car_camry_main.id]
    assert camry_element_diff.action is DiffAction.REMOVED
    props_by_type = {p.property_type: p for p in camry_element_diff.properties}
    _assert_removed_property_diffs(
        props_by_type,
        (
            (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ),
    )

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
    _assert_added_property_diffs(
        props_by_type,
        (
            (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ),
    )

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
    _assert_added_property_diffs(
        props_by_type,
        (
            (DatabaseEdgeType.IS_RELATED, car_camry_main.id),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ),
    )

    # test new car that was migrated on the branch
    branch_car_diff = nodes_by_id_and_kind[branch_car.id, "Test2NewCar"]
    assert branch_car_diff.action is DiffAction.ADDED
    assert branch_car_diff.is_node_kind_migration is True
    attr_diffs_by_name = {a.name: a for a in branch_car_diff.attributes}
    assert set(attr_diffs_by_name) == {
        "name",
        "nbr_seats",
        "is_electric",
        "color",
        "transmission",
        "human_friendly_id",
        "display_label",
    }
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
            DatabaseEdgeType.IS_PROTECTED,
        }
        _assert_added_property_diffs(
            props_by_type,
            [
                (DatabaseEdgeType.HAS_VALUE, expected_value),
                (DatabaseEdgeType.IS_PROTECTED, False),
            ],
        )
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
    }
    _assert_added_property_diffs(
        properties_by_type,
        (
            (DatabaseEdgeType.IS_PROTECTED, False),
            (DatabaseEdgeType.IS_RELATED, person_jane_main.id),
        ),
    )

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
    }
    _assert_removed_property_diffs(
        properties_by_type,
        (
            (DatabaseEdgeType.IS_PROTECTED, False),
            (DatabaseEdgeType.IS_RELATED, person_jane_main.id),
        ),
    )

    # validate new camry that was updated on branch before migration
    new_camry_diff = nodes_by_id_and_kind[car_camry_main.id, "Test2NewCar"]
    assert new_camry_diff.action is DiffAction.ADDED
    assert new_camry_diff.is_node_kind_migration is True
    attr_diffs_by_name = {a.name: a for a in new_camry_diff.attributes}
    assert set(attr_diffs_by_name) == {"nbr_seats", "color", "display_label"}
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
        else:
            assert value_diff_prop.previous_value == f"camry {car_camry_main.color.value}"
            assert value_diff_prop.new_value == f"camry {new_branch_camry_color}"

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
    }
    _assert_added_property_diffs(
        properties_by_type,
        (
            (DatabaseEdgeType.IS_PROTECTED, False),
            (DatabaseEdgeType.IS_RELATED, new_branch_camry_owner_id),
        ),
    )
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
    }
    _assert_added_property_diffs(
        properties_by_type,
        (
            (DatabaseEdgeType.IS_PROTECTED, False),
            (DatabaseEdgeType.IS_RELATED, new_branch_camry_driver_id),
        ),
    )

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
    assert set(attr_diffs_by_name.keys()) == {"color", "human_friendly_id", "name", "display_label"}
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
    assert set(attr_diffs_by_name.keys()) == {"color", "human_friendly_id", "name", "display_label"}
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
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_camry_main: Node,
    person_john_main: Node,
    person_jane_main: Node,
) -> None:
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

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
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
            DatabaseEdgeType.IS_PROTECTED,
        }
        for property_type, value in (
            (DatabaseEdgeType.HAS_VALUE, car_accord_main.color.value),
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
            DatabaseEdgeType.IS_PROTECTED,
        }
        for property_type, value in (
            (DatabaseEdgeType.HAS_VALUE, car_accord_main.color.value),
            (DatabaseEdgeType.IS_PROTECTED, False),
        ):
            diff_prop = props_by_type[property_type]
            assert diff_prop.action is DiffAction.ADDED
            assert diff_prop.new_value == value
            assert diff_prop.previous_value is None

    base_diff = calculated_diffs.base_branch_diff
    assert len(base_diff.nodes) == 0


async def test_calculate_with_renamed_relationships(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_camry_main: Node,
    person_john_main: Node,
    person_jane_main: Node,
) -> None:
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
            DatabaseEdgeType.IS_PROTECTED,
        }
        for property_type, value in (
            (DatabaseEdgeType.IS_RELATED, peer_id),
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
            DatabaseEdgeType.IS_PROTECTED,
        }
        for property_type, value in (
            (DatabaseEdgeType.IS_RELATED, peer_id),
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
            DatabaseEdgeType.IS_PROTECTED,
        }
        for property_type, value in (
            (DatabaseEdgeType.IS_RELATED, peer_id),
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
            DatabaseEdgeType.IS_PROTECTED,
        }
        for property_type, value in (
            (DatabaseEdgeType.IS_RELATED, peer_id),
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
    car_accord_main: Node,
    car_camry_main: Node,
    person_john_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
    person_albert_main: Node,
) -> None:
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
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
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
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
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
    car_accord_main: Node,
    car_camry_main: Node,
    person_john_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="lets-migrate")

    # property-level changes before migration
    branch_john = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
    branch_john.name.value = "John Branch"
    await branch_john.save(db=db)
    branch_accord = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await branch_accord.owner.update(db=db, data={"id": person_john_main.id, "_relation__is_protected": True})
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
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
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
    assert set(attributes_by_name.keys()) == {"human_friendly_id", "name", "display_label"}
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
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_PROTECTED}
    is_protected_prop = properties_by_type[DatabaseEdgeType.IS_PROTECTED]
    assert is_protected_prop.action is DiffAction.UPDATED
    assert is_protected_prop.new_value is True
    assert is_protected_prop.previous_value is False

    # validate person_jane_main migrated
    jane_previous_diff = [n for n in nodes_by_id[person_jane_main.id] if n.action is DiffAction.REMOVED][0]
    jane_new_diff = [n for n in nodes_by_id[person_jane_main.id] if n.action is DiffAction.ADDED][0]
    assert jane_previous_diff.is_node_kind_migration is True
    assert jane_previous_diff.attributes == []
    assert jane_previous_diff.relationships == []
    assert jane_new_diff.is_node_kind_migration is True
    attributes_by_name = {a.name: a for a in jane_new_diff.attributes}
    assert set(attributes_by_name.keys()) == {"human_friendly_id", "name", "display_label"}
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
    assert set(properties_by_type.keys()) == {DatabaseEdgeType.IS_PROTECTED}
    is_protected_prop = properties_by_type[DatabaseEdgeType.IS_PROTECTED]
    assert is_protected_prop.action is DiffAction.UPDATED
    assert is_protected_prop.new_value is True
    assert is_protected_prop.previous_value is False

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
    car_accord_main: Node,
    car_camry_main: Node,
    person_john_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
    person_albert_main: Node,
) -> None:
    """Test that when a schema kind is migrated on the default branch, relationships to instances
    of the migrated node can be updated on a branch before the diff is calculated.
    """
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
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
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
        DatabaseEdgeType.IS_PROTECTED,
    }
    for prop_type, previous_value in [
        (DatabaseEdgeType.IS_RELATED, person_john_main.id),
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


async def test_relationship_property_added_on_source_branch_kind_migration(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    person_john_main: Node,
    person_alfred_main: Node,
) -> None:
    """Validate diff for relationship when peer kind is migrated on the branch after branch forks
    and the source property is updated on the branch
    """
    branch = await create_branch(db=db, branch_name="branch-src-migration-rel-prop")
    from_time = Timestamp(branch.created_at)

    # Migrate TestCar -> Test2NewCar on the branch.
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    new_car_schema = schema.get(name="TestCar", duplicate=True)
    new_car_schema.name = "NewCar"
    new_car_schema.namespace = "Test2"
    assert new_car_schema.kind == "Test2NewCar"
    registry.schema.set(name="Test2NewCar", schema=new_car_schema, branch=branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"),
    )
    assert not (await migration.execute(migration_input=MigrationInput(db=db), branch=branch)).errors

    # Set car_accord.owner.source = alfred on the branch (branch owns the HAS_SOURCE edge).
    migrated_car = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await migrated_car.owner.update(db=db, data={"id": person_john_main.id, "_relation__source": person_alfred_main.id})
    await migrated_car.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    # Must not raise DiffNoPeerIdError.
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    branch_diff = calculated_diffs.diff_branch_diff
    car_nodes = [n for n in branch_diff.nodes if n.uuid == car_accord_main.id]
    assert car_nodes, "branch diff should include the car node whose owner source was set"
    owner_rel_diffs = [r for car in car_nodes for r in car.relationships if r.name == "owner"]
    assert owner_rel_diffs, "branch diff for car should include the owner relationship change"
    # The peer must be resolvable — i.e. the IS_RELATED peer row was emitted.
    found_peer_with_source = False
    for rel in owner_rel_diffs:
        for elem in rel.relationships:
            # The single_relationship's peer_id is populated from the IS_RELATED property row.
            assert elem.peer_id, (
                "peer_id must be set on the owner relationship element — missing IS_RELATED peer "
                "row would have triggered DiffNoPeerIdError during parse"
            )
            prop_types = {p.property_type for p in elem.properties}
            if DatabaseEdgeType.HAS_SOURCE in prop_types:
                assert DatabaseEdgeType.IS_RELATED in prop_types, (
                    "HAS_SOURCE property change must be accompanied by an IS_RELATED peer row"
                )
                found_peer_with_source = True
                assert elem.peer_id == person_john_main.id
    assert found_peer_with_source, "expected at least one owner relationship element with a HAS_SOURCE change"


async def test_relationship_property_branch_change_with_target_branch_kind_migration(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    person_john_main: Node,
    person_alfred_main: Node,
) -> None:
    """Validate diff for relationship source when one of the peers is migrated to a new kind on the target branch
    after branch forks
    """
    branch = await create_branch(db=db, branch_name="branch-tgt-migration-rel-prop")
    from_time = Timestamp(branch.created_at)

    # Target-branch migration: TestCar -> Test2NewCar on the default branch AFTER the fork.
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    new_car_schema = schema.get(name="TestCar", duplicate=True)
    new_car_schema.name = "NewCar"
    new_car_schema.namespace = "Test2"
    assert new_car_schema.kind == "Test2NewCar"
    registry.schema.set(name="Test2NewCar", schema=new_car_schema, branch=default_branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"),
    )
    assert not (await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)).errors

    # On the diff branch (still sees TestCar), set owner.source = alfred.
    branch_car = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    await branch_car.owner.update(db=db, data={"id": person_john_main.id, "_relation__source": person_alfred_main.id})
    await branch_car.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    branch_diff = calculated_diffs.diff_branch_diff
    # Every DiffNode for car_accord.id must carry a resolvable peer on the owner relationship.
    for node in branch_diff.nodes:
        if node.uuid != car_accord_main.id:
            continue
        for rel in node.relationships:
            if rel.name != "owner":
                continue
            for elem in rel.relationships:
                prop_types = {p.property_type for p in elem.properties}
                if DatabaseEdgeType.HAS_SOURCE not in prop_types:
                    continue
                assert DatabaseEdgeType.IS_RELATED in prop_types, (
                    f"DiffNode(uuid={node.uuid}, kind={node.kind}): owner property group has "
                    f"HAS_SOURCE but no IS_RELATED peer row"
                )
                assert elem.peer_id, f"DiffNode(uuid={node.uuid}, kind={node.kind}): peer_id must be set"


async def test_cleared_attribute_property_with_target_branch_kind_migration(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    person_john_main: Node,
    person_alfred_main: Node,
) -> None:
    """A pre-fork HAS_SOURCE that the branch clears must surface in the diff
    even when the target branch ran a node-kind migration after the fork.
    """
    # Set name.source = alfred on main before fork so the branch has a
    # pre-existing source to clear.
    main_car = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id)
    main_car.name.source = person_alfred_main
    await main_car.save(db=db)

    branch = await create_branch(db=db, branch_name="branch-tgt-migration-cleared-prop")
    from_time = Timestamp(branch.created_at)

    # Target-branch migration: TestCar -> Test2NewCar on the default branch AFTER the fork.
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    new_car_schema = schema.get(name="TestCar", duplicate=True)
    new_car_schema.name = "NewCar"
    new_car_schema.namespace = "Test2"
    assert new_car_schema.kind == "Test2NewCar"
    registry.schema.set(name="Test2NewCar", schema=new_car_schema, branch=default_branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"),
    )
    assert not (await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)).errors

    # Clear name.source on the diff branch.
    branch_car = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
    branch_car.name.clear_source()
    await branch_car.save(db=db)

    diff_calculator = DiffCalculator(db=db)
    calculated_diffs = await diff_calculator.calculate_diff(
        base_branch=default_branch,
        diff_branch=branch,
        from_time=from_time,
        to_time=Timestamp(),
        include_unchanged=False,
    )

    branch_diff = calculated_diffs.diff_branch_diff
    car_nodes = [n for n in branch_diff.nodes if n.uuid == car_accord_main.id]
    assert car_nodes, "branch diff should include the car node whose name.source was cleared"

    name_attrs = [a for car in car_nodes for a in car.attributes if a.name == "name"]
    assert name_attrs, "branch diff for car should include the ``name`` attribute"

    has_source_props = [p for a in name_attrs for p in a.properties if p.property_type is DatabaseEdgeType.HAS_SOURCE]
    assert has_source_props, "branch diff for name attribute should include a HAS_SOURCE property change"
    prop = has_source_props[0]
    assert prop.action is DiffAction.REMOVED, f"expected HAS_SOURCE action=REMOVED, got {prop.action}"
    assert prop.previous_value == person_alfred_main.id, (
        f"expected HAS_SOURCE previous_value=alfred, got {prop.previous_value}"
    )
    assert prop.new_value is None, f"expected HAS_SOURCE new_value=None, got {prop.new_value}"
