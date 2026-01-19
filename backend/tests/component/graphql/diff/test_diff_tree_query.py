from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from infrahub.core.branch import Branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.diff.query.diff_summary import DiffSummaryCounters
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from infrahub.graphql.enums import ConflictSelection as GraphQLConfictSelection
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

ADDED_ACTION = "ADDED"
UPDATED_ACTION = "UPDATED"
REMOVED_ACTION = "REMOVED"
UNCHANGED_ACTION = "UNCHANGED"
CARDINALITY_ONE = "ONE"
CARDINALITY_MANY = "MANY"
IS_RELATED_TYPE = "IS_RELATED"
IS_PROTECTED_TYPE = "IS_PROTECTED"

DIFF_TREE_QUERY = """
query GetDiffTree($branch: String){
    DiffTree (branch: $branch, filters: {status: {excludes: UNCHANGED}}) {
        base_branch
        diff_branch
        from_time
        to_time
        num_added
        num_removed
        num_updated
        num_conflicts
        num_untracked_base_changes
        num_untracked_diff_changes
        nodes {
            uuid
            kind
            label
            last_changed_at
            status
            parent {
              uuid
              kind
              relationship_name
            }
            contains_conflict
            num_added
            num_removed
            num_updated
            num_conflicts
            attributes {
                name
                last_changed_at
                status
                num_added
                num_removed
                num_updated
                num_conflicts
                contains_conflict
                conflict {
                    uuid
                    base_branch_action
                    base_branch_value
                    base_branch_changed_at
                    base_branch_label
                    diff_branch_action
                    diff_branch_value
                    diff_branch_changed_at
                    diff_branch_label
                    selected_branch
                }
                properties {
                    property_type
                    last_changed_at
                    previous_value
                    new_value
                    previous_label
                    new_label
                    status
                    conflict {
                        uuid
                        base_branch_action
                        base_branch_value
                        base_branch_changed_at
                        base_branch_label
                        diff_branch_action
                        diff_branch_value
                        diff_branch_changed_at
                        diff_branch_label
                        selected_branch
                    }
                }
            }
            relationships {
                name
                last_changed_at
                status
                cardinality
                contains_conflict
                elements {
                    status
                    peer_id
                    last_changed_at
                    contains_conflict
                    conflict {
                        uuid
                        base_branch_action
                        base_branch_changed_at
                        base_branch_value
                        base_branch_label
                        diff_branch_action
                        diff_branch_value
                        diff_branch_changed_at
                        diff_branch_label
                        selected_branch
                    }
                    properties {
                        property_type
                        last_changed_at
                        previous_value
                        new_value
                        previous_label
                        new_label
                        status
                        conflict {
                            uuid
                            base_branch_action
                            base_branch_value
                            base_branch_changed_at
                            base_branch_label
                            diff_branch_action
                            diff_branch_value
                            diff_branch_changed_at
                            diff_branch_label
                            selected_branch
                        }
                    }
                }
            }
        }
    }
}
"""

DIFF_TREE_QUERY_FILTERS = """
query ($branch: String, $filters: DiffTreeQueryFilters){
    DiffTree (branch: $branch, filters: $filters) {
        nodes {
            uuid
            kind
            label
            status
        }
    }
}
"""

DIFF_TREE_QUERY_SUMMARY = """
query GetDiffTreeSummary($branch: String, $filters: DiffTreeQueryFilters){
    DiffTreeSummary (branch: $branch, filters: $filters) {
        base_branch
        diff_branch
        from_time
        to_time
        num_added
        num_removed
        num_updated
        num_conflicts
        num_unchanged
        num_untracked_base_changes
        num_untracked_diff_changes
    }
}
"""

DIFF_TREE_QUERY_BY_PROPOSED_CHANGE = """
query ($branch: String, $proposed_change_id: String){
    DiffTree (branch: $branch, proposed_change_id: $proposed_change_id) {
        nodes {
            uuid
            kind
            label
            status
        }
    }
}
"""

DIFF_TREE_SUMMARY_QUERY_BY_PROPOSED_CHANGE = """
query ($branch: String, $proposed_change_id: String){
    DiffTreeSummary (branch: $branch, proposed_change_id: $proposed_change_id) {
        base_branch
        diff_branch
        num_added
        num_removed
        num_updated
        num_conflicts
        num_unchanged
    }
}
"""

DIFF_TREE_QUERY_ALL_FILTERS = """
query ($branch: String, $from_time: DateTime, $to_time: DateTime, $proposed_change_id: String){
    DiffTree (branch: $branch, from_time: $from_time, to_time: $to_time, proposed_change_id: $proposed_change_id) {
        from_time
        to_time
        name
        nodes {
            uuid
            kind
            label
            status
        }
    }
}
"""


@pytest.fixture
async def diff_branch(db: InfrahubDatabase, default_branch: Branch) -> Branch:
    return await create_branch(db=db, branch_name="branch")


@pytest.fixture
async def diff_repository(db: InfrahubDatabase, diff_branch: Branch) -> DiffRepository:
    component_registry = get_component_registry()
    repository = await component_registry.get_component(DiffRepository, db=db, branch=diff_branch)
    return repository


@pytest.fixture
async def diff_coordinator(db: InfrahubDatabase, diff_branch: Branch) -> DiffCoordinator:
    component_registry = get_component_registry()
    coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=diff_branch)
    coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
    coordinator.data_check_synchronizer.synchronize.return_value = []
    return coordinator


async def test_diff_tree_no_changes(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_low,
    diff_coordinator: DiffCoordinator,
    diff_branch: Branch,
) -> None:
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(
        base_branch=default_branch, diff_branch=diff_branch
    )
    from_time = Timestamp(diff_branch.branched_from)
    to_time = enriched_diff_metadata.to_time

    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )

    assert result.errors is None
    assert result.data
    assert result.data["DiffTree"] == {
        "base_branch": default_branch.name,
        "diff_branch": diff_branch.name,
        "from_time": from_time.to_datetime().isoformat(),
        "to_time": to_time.to_datetime().isoformat(),
        "num_added": 0,
        "num_removed": 0,
        "num_updated": 0,
        "num_conflicts": 0,
        "num_untracked_base_changes": 0,
        "num_untracked_diff_changes": 0,
        "nodes": [],
    }


async def test_diff_tree_no_diffs(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema, diff_branch: Branch
) -> None:
    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )

    assert result.errors is None
    assert result.data
    assert result.data["DiffTree"] is None


async def test_diff_tree_no_branch(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema
) -> None:
    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": "wheres-that-branch"},
    )

    assert result.errors
    assert "wheres-that-branch not found" in result.errors[0].message


async def test_diff_tree_one_attr_change(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema: NodeSchema,
    criticality_low,
    diff_branch: Branch,
    diff_coordinator: DiffCoordinator,
    diff_repository: DiffRepository,
) -> None:
    main_crit = await NodeManager.get_one(db=db, id=criticality_low.id, branch=default_branch)
    main_crit.color.value = "#fedcba"
    branch_crit = await NodeManager.get_one(db=db, id=criticality_low.id, branch=diff_branch)
    branch_crit.color.value = "#abcdef"
    before_change_datetime = Timestamp()
    await main_crit.save(db=db)
    await branch_crit.save(db=db)
    after_change_datetime = Timestamp()

    enriched_diff_metadata = await diff_coordinator.update_branch_diff(
        base_branch=default_branch, diff_branch=diff_branch
    )
    enriched_diff = await diff_repository.get_one(
        diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
    )

    enriched_conflict_map = enriched_diff.get_all_conflicts()
    enriched_conflict = list(enriched_conflict_map.values())[0]
    await diff_repository.update_conflict_by_id(
        conflict_id=enriched_conflict.uuid, selection=ConflictSelection.DIFF_BRANCH
    )
    # add some untracked changes
    main_crit = await NodeManager.get_one(db=db, id=criticality_low.id, branch=default_branch)
    main_crit.color.value = "blurple"
    branch_crit = await NodeManager.get_one(db=db, id=criticality_low.id, branch=diff_branch)
    branch_crit.color.value = "walrus"
    await main_crit.save(db=db)
    await branch_crit.save(db=db)

    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )
    from_time = Timestamp(diff_branch.branched_from)
    to_time = enriched_diff_metadata.to_time

    assert result.errors is None

    assert result.data
    assert result.data["DiffTree"]
    assert result.data["DiffTree"]["nodes"]
    node_diff = result.data["DiffTree"]["nodes"][0]
    node_changed_at = node_diff["last_changed_at"]
    assert Timestamp(node_changed_at) < before_change_datetime
    assert node_diff["attributes"]
    attribute_diff = node_diff["attributes"][0]
    attribute_changed_at = attribute_diff["last_changed_at"]
    assert Timestamp(attribute_changed_at) < before_change_datetime
    assert attribute_diff["properties"]
    property_diff = attribute_diff["properties"][0]
    property_changed_at = property_diff["last_changed_at"]
    assert before_change_datetime < Timestamp(property_changed_at) < after_change_datetime
    assert result.data["DiffTree"] == {
        "base_branch": "main",
        "diff_branch": diff_branch.name,
        "from_time": from_time.to_datetime().isoformat(),
        "to_time": to_time.to_datetime().isoformat(),
        "num_added": 0,
        "num_removed": 0,
        "num_updated": 1,
        "num_conflicts": 1,
        "num_untracked_base_changes": 2,
        "num_untracked_diff_changes": 2,
        "nodes": [
            {
                "uuid": criticality_low.id,
                "kind": criticality_low.get_kind(),
                "label": "Low",
                "last_changed_at": node_changed_at,
                "num_added": 0,
                "num_removed": 0,
                "num_updated": 1,
                "num_conflicts": 1,
                "parent": None,
                "status": UPDATED_ACTION,
                "contains_conflict": True,
                "relationships": [],
                "attributes": [
                    {
                        "name": "color",
                        "last_changed_at": attribute_changed_at,
                        "num_added": 0,
                        "num_removed": 0,
                        "num_updated": 1,
                        "num_conflicts": 1,
                        "status": UPDATED_ACTION,
                        "contains_conflict": True,
                        "conflict": {
                            "uuid": enriched_conflict.uuid,
                            "base_branch_action": UPDATED_ACTION,
                            "base_branch_value": "#fedcba",
                            "base_branch_changed_at": enriched_conflict.base_branch_changed_at.to_string(with_z=False),
                            "base_branch_label": None,
                            "diff_branch_action": UPDATED_ACTION,
                            "diff_branch_value": "#abcdef",
                            "diff_branch_changed_at": enriched_conflict.diff_branch_changed_at.to_string(with_z=False),
                            "diff_branch_label": None,
                            "selected_branch": GraphQLConfictSelection.DIFF_BRANCH.name,
                        },
                        "properties": [
                            {
                                "property_type": "HAS_VALUE",
                                "last_changed_at": property_changed_at,
                                "previous_value": criticality_low.color.value,
                                "new_value": "#abcdef",
                                "previous_label": None,
                                "new_label": None,
                                "status": UPDATED_ACTION,
                                "conflict": None,
                            }
                        ],
                    }
                ],
            }
        ],
    }


async def test_diff_tree_one_relationship_change(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    car_accord_main: Node,
    person_john_main: Node,
    person_jane_main: Node,
    diff_branch: Branch,
    diff_coordinator: DiffCoordinator,
    diff_repository: DiffRepository,
) -> None:
    branch_car = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=diff_branch)
    await branch_car.owner.update(db=db, data=[person_jane_main])
    before_change_datetime = Timestamp()
    await branch_car.save(db=db)
    after_change_datetime = Timestamp()
    accord_label = await branch_car.get_display_label(db=db)
    john_label = await person_john_main.get_display_label(db=db)
    jane_label = await person_jane_main.get_display_label(db=db)

    enriched_diff_metadata = await diff_coordinator.update_branch_diff(
        base_branch=default_branch, diff_branch=diff_branch
    )
    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )
    from_time = Timestamp(diff_branch.branched_from)
    to_time = enriched_diff_metadata.to_time

    assert result.errors is None

    assert result.data
    assert result.data["DiffTree"]
    diff_tree_response = result.data["DiffTree"].copy()
    nodes_response = diff_tree_response.pop("nodes")
    assert diff_tree_response == {
        "base_branch": "main",
        "diff_branch": diff_branch.name,
        "from_time": from_time.to_datetime().isoformat(),
        "to_time": to_time.to_datetime().isoformat(),
        "num_added": 0,
        "num_removed": 0,
        "num_updated": 3,
        "num_conflicts": 0,
        "num_untracked_base_changes": 0,
        "num_untracked_diff_changes": 0,
    }
    assert len(nodes_response) == 3
    node_response_by_id = {n["uuid"]: n for n in nodes_response}
    assert set(node_response_by_id.keys()) == {car_accord_main.id, person_john_main.id, person_jane_main.id}
    # car node
    car_response = node_response_by_id[car_accord_main.id]
    car_relationship_response = car_response.pop("relationships")
    car_changed_at = car_response["last_changed_at"]
    assert Timestamp(car_changed_at) < before_change_datetime
    assert car_response == {
        "uuid": car_accord_main.id,
        "kind": car_accord_main.get_kind(),
        "label": await car_accord_main.get_display_label(db=db),
        "last_changed_at": car_changed_at,
        "num_added": 0,
        "num_removed": 0,
        "num_updated": 1,
        "num_conflicts": 0,
        "parent": {"kind": person_jane_main.get_kind(), "relationship_name": "cars", "uuid": person_jane_main.get_id()},
        "status": UPDATED_ACTION,
        "contains_conflict": False,
        "attributes": [],
    }
    car_relationships_by_name = {r["name"]: r for r in car_relationship_response}
    assert set(car_relationships_by_name.keys()) == {"owner"}
    owner_rel = car_relationships_by_name["owner"]
    owner_changed_at = owner_rel["last_changed_at"]
    assert before_change_datetime < Timestamp(owner_changed_at) < after_change_datetime
    owner_elements = owner_rel.pop("elements")
    assert owner_rel == {
        "name": "owner",
        "last_changed_at": owner_changed_at,
        "status": UPDATED_ACTION,
        "cardinality": "ONE",
        "contains_conflict": False,
    }
    assert len(owner_elements) == 1
    owner_element = owner_elements[0]
    owner_element_changed_at = owner_element["last_changed_at"]
    assert before_change_datetime < Timestamp(owner_element_changed_at) < after_change_datetime
    owner_properties = owner_element.pop("properties")
    assert owner_element == {
        "status": UPDATED_ACTION,
        "peer_id": person_jane_main.id,
        "last_changed_at": owner_element_changed_at,
        "contains_conflict": False,
        "conflict": None,
    }
    owner_properties_by_type = {p["property_type"]: p for p in owner_properties}
    assert set(owner_properties_by_type.keys()) == {IS_RELATED_TYPE, IS_PROTECTED_TYPE}
    owner_prop = owner_properties_by_type[IS_RELATED_TYPE]
    owner_prop_changed_at = owner_prop["last_changed_at"]
    assert before_change_datetime < Timestamp(owner_prop_changed_at) < after_change_datetime
    assert owner_prop == {
        "property_type": IS_RELATED_TYPE,
        "last_changed_at": owner_prop_changed_at,
        "previous_value": person_john_main.id,
        "new_value": person_jane_main.id,
        "previous_label": john_label,
        "new_label": jane_label,
        "status": UPDATED_ACTION,
        "conflict": None,
    }
    owner_prop = owner_properties_by_type[IS_RELATED_TYPE]
    owner_prop_changed_at = owner_prop["last_changed_at"]
    assert before_change_datetime < Timestamp(owner_prop_changed_at) < after_change_datetime
    assert owner_prop == {
        "property_type": IS_RELATED_TYPE,
        "last_changed_at": owner_prop_changed_at,
        "previous_value": person_john_main.id,
        "new_value": person_jane_main.id,
        "previous_label": john_label,
        "new_label": jane_label,
        "status": UPDATED_ACTION,
        "conflict": None,
    }
    # john node
    john_response = node_response_by_id[person_john_main.id]
    john_relationship_response = john_response.pop("relationships")
    john_changed_at = john_response["last_changed_at"]
    assert Timestamp(john_changed_at) < before_change_datetime
    assert john_response == {
        "uuid": person_john_main.id,
        "kind": person_john_main.get_kind(),
        "label": await person_john_main.get_display_label(db=db),
        "last_changed_at": john_changed_at,
        "num_added": 0,
        "num_removed": 0,
        "num_updated": 1,
        "num_conflicts": 0,
        "parent": None,
        "status": UPDATED_ACTION,
        "contains_conflict": False,
        "attributes": [],
    }
    john_relationships_by_name = {r["name"]: r for r in john_relationship_response}
    assert set(john_relationships_by_name.keys()) == {"cars"}
    cars_rel = john_relationships_by_name["cars"]
    cars_changed_at = cars_rel["last_changed_at"]
    assert before_change_datetime < Timestamp(cars_changed_at) < after_change_datetime
    cars_elements = cars_rel.pop("elements")
    assert cars_rel == {
        "name": "cars",
        "last_changed_at": cars_changed_at,
        "status": UPDATED_ACTION,
        "cardinality": "MANY",
        "contains_conflict": False,
    }
    assert len(cars_elements) == 1
    cars_element = cars_elements[0]
    cars_element_changed_at = cars_element["last_changed_at"]
    assert before_change_datetime < Timestamp(cars_element_changed_at) < after_change_datetime
    cars_properties = cars_element.pop("properties")
    assert cars_element == {
        "status": REMOVED_ACTION,
        "peer_id": car_accord_main.id,
        "last_changed_at": cars_element_changed_at,
        "contains_conflict": False,
        "conflict": None,
    }
    cars_properties_by_type = {p["property_type"]: p for p in cars_properties}
    assert set(cars_properties_by_type.keys()) == {IS_RELATED_TYPE, IS_PROTECTED_TYPE}
    for property_type, previous_value, previous_label in [
        (IS_RELATED_TYPE, car_accord_main.id, accord_label),
        (IS_PROTECTED_TYPE, "False", None),
    ]:
        cars_prop = cars_properties_by_type[property_type]
        cars_prop_changed_at = cars_prop["last_changed_at"]
        assert before_change_datetime < Timestamp(cars_prop_changed_at) < after_change_datetime
        assert cars_prop == {
            "property_type": property_type,
            "last_changed_at": cars_prop_changed_at,
            "previous_value": previous_value,
            "previous_label": previous_label,
            "new_value": None,
            "new_label": None,
            "status": REMOVED_ACTION,
            "conflict": None,
        }
    # jane node
    jane_response = node_response_by_id[person_jane_main.id]
    jane_relationship_response = jane_response.pop("relationships")
    jane_changed_at = jane_response["last_changed_at"]
    assert Timestamp(jane_changed_at) < before_change_datetime
    assert jane_response == {
        "uuid": person_jane_main.id,
        "kind": person_jane_main.get_kind(),
        "label": await person_jane_main.get_display_label(db=db),
        "last_changed_at": jane_changed_at,
        "num_added": 0,
        "num_removed": 0,
        "num_updated": 1,
        "num_conflicts": 0,
        "parent": None,
        "status": UPDATED_ACTION,
        "contains_conflict": False,
        "attributes": [],
    }
    jane_relationships_by_name = {r["name"]: r for r in jane_relationship_response}
    assert set(jane_relationships_by_name.keys()) == {"cars"}
    cars_rel = jane_relationships_by_name["cars"]
    cars_changed_at = cars_rel["last_changed_at"]
    assert before_change_datetime < Timestamp(cars_changed_at) < after_change_datetime
    cars_elements = cars_rel.pop("elements")
    assert cars_rel == {
        "name": "cars",
        "last_changed_at": cars_changed_at,
        "status": UPDATED_ACTION,
        "cardinality": "MANY",
        "contains_conflict": False,
    }
    assert len(cars_elements) == 1
    cars_element = cars_elements[0]
    cars_element_changed_at = cars_element["last_changed_at"]
    assert before_change_datetime < Timestamp(cars_element_changed_at) < after_change_datetime
    cars_properties = cars_element.pop("properties")
    assert cars_element == {
        "status": ADDED_ACTION,
        "peer_id": car_accord_main.id,
        "last_changed_at": cars_element_changed_at,
        "contains_conflict": False,
        "conflict": None,
    }
    cars_properties_by_type = {p["property_type"]: p for p in cars_properties}
    assert set(cars_properties_by_type.keys()) == {IS_RELATED_TYPE, IS_PROTECTED_TYPE}
    for property_type, new_value, new_label in [
        (IS_RELATED_TYPE, car_accord_main.id, accord_label),
        (IS_PROTECTED_TYPE, "False", None),
    ]:
        cars_prop = cars_properties_by_type[property_type]
        cars_prop_changed_at = cars_prop["last_changed_at"]
        assert before_change_datetime < Timestamp(cars_prop_changed_at) < after_change_datetime
        assert cars_prop == {
            "property_type": property_type,
            "last_changed_at": cars_prop_changed_at,
            "previous_value": None,
            "previous_label": None,
            "new_value": new_value,
            "new_label": new_label,
            "status": ADDED_ACTION,
            "conflict": None,
        }


async def test_diff_tree_hierarchy_change(
    db: InfrahubDatabase,
    default_branch: Branch,
    hierarchical_location_data,
    diff_branch: Branch,
    diff_coordinator: DiffCoordinator,
) -> None:
    europe_main = hierarchical_location_data["europe"]
    paris_main = hierarchical_location_data["paris"]
    rack1_main = hierarchical_location_data["paris-r1"]
    rack1_main = hierarchical_location_data["paris-r1"]
    rack2_main = hierarchical_location_data["paris-r2"]

    rack1_branch = await NodeManager.get_one(db=db, id=rack1_main.id, branch=diff_branch)
    rack1_branch.status.value = "offline"
    rack2_branch = await NodeManager.get_one(db=db, id=rack2_main.id, branch=diff_branch)
    rack2_branch.name.value = "paris rack2"

    await rack1_branch.save(db=db)
    await rack2_branch.save(db=db)

    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch)
    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )

    assert result.errors is None
    assert result.data
    assert len(result.data["DiffTree"]["nodes"]) == 4

    nodes_parent = {node["label"]: node["parent"] for node in result.data["DiffTree"]["nodes"]}
    expected_nodes_parent = {
        "paris": {"uuid": europe_main.id, "kind": "LocationRegion", "relationship_name": "children"},
        "paris rack2": {"uuid": paris_main.id, "kind": "LocationSite", "relationship_name": "children"},
        "paris-r1": {"uuid": paris_main.id, "kind": "LocationSite", "relationship_name": "children"},
        "europe": None,
    }
    assert nodes_parent == expected_nodes_parent


async def test_diff_tree_summary_no_diffs(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema, diff_branch: Branch
) -> None:
    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_SUMMARY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )

    assert result.errors is None
    assert result.data
    assert result.data["DiffTreeSummary"] is None


async def test_diff_tree_summary_no_changes(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_low,
    diff_coordinator: DiffCoordinator,
    diff_branch: Branch,
) -> None:
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(
        base_branch=default_branch, diff_branch=diff_branch
    )
    from_time = Timestamp(diff_branch.branched_from)
    to_time = enriched_diff_metadata.to_time

    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_SUMMARY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )

    assert result.errors is None
    assert result.data
    assert result.data["DiffTreeSummary"] == {
        "base_branch": default_branch.name,
        "diff_branch": diff_branch.name,
        "from_time": from_time.to_datetime().isoformat(),
        "to_time": to_time.to_datetime().isoformat(),
        "num_added": 0,
        "num_removed": 0,
        "num_updated": 0,
        "num_unchanged": 0,
        "num_conflicts": 0,
        "num_untracked_base_changes": 0,
        "num_untracked_diff_changes": 0,
    }


@pytest.mark.parametrize(
    "filters,counters",
    [
        pytest.param(
            {},
            DiffSummaryCounters(
                num_added=4,
                num_updated=9,
                num_removed=4,
                from_time=Timestamp(datetime.now(UTC).isoformat()),
                to_time=Timestamp(datetime.now(UTC).isoformat()),
            ),
            id="no-filters",
        ),
        pytest.param(
            {"kind": {"includes": ["TestThing"]}},
            DiffSummaryCounters(
                num_added=4,
                num_updated=3,
                num_removed=4,
                from_time=Timestamp(datetime.now(UTC).isoformat()),
                to_time=Timestamp(datetime.now(UTC).isoformat()),
            ),
            id="kind-includes",
        ),
    ],
)
async def test_diff_summary_filters(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data, filters, counters: DiffSummaryCounters
) -> None:
    rack1_main = hierarchical_location_data["paris-r1"]
    rack2_main = hierarchical_location_data["paris-r2"]

    thing1_main = await Node.init(db=db, schema="TestThing")
    await thing1_main.new(db=db, name="thing1", location=rack1_main)
    await thing1_main.save(db=db)

    thing2_main = await Node.init(db=db, schema="TestThing")
    await thing2_main.new(db=db, name="thing2", location=rack2_main)
    await thing2_main.save(db=db)

    diff_branch = await create_branch(db=db, branch_name="diff")

    thing3_branch = await Node.init(db=db, schema="TestThing", branch=diff_branch)
    await thing3_branch.new(db=db, name="thing3", location=rack1_main)
    await thing3_branch.save(db=db)

    rack1_branch = await NodeManager.get_one(db=db, id=rack1_main.id, branch=diff_branch)
    rack1_branch.status.value = "offline"
    rack2_branch = await NodeManager.get_one(db=db, id=rack2_main.id, branch=diff_branch)
    rack2_branch.name.value = "paris rack2"

    await rack1_branch.save(db=db)
    await rack2_branch.save(db=db)

    thing1_branch = await NodeManager.get_one(db=db, id=thing1_main.id, branch=diff_branch)
    thing1_branch.name.value = "THING1"
    await thing1_branch.save(db=db)

    thing2_branch = await NodeManager.get_one(db=db, id=thing2_main.id, branch=diff_branch)
    await thing2_branch.delete(db=db)

    # ----------------------------
    # Generate Diff in DB
    # ----------------------------
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=diff_branch)
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(
        base_branch=default_branch, diff_branch=diff_branch
    )
    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)

    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_SUMMARY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name, "filters": filters},
    )

    assert result.errors is None
    counters.from_time = enriched_diff_metadata.from_time
    counters.to_time = enriched_diff_metadata.to_time
    assert result.data
    diff: dict = result.data["DiffTreeSummary"]
    from_timestamp = Timestamp(result.data["DiffTreeSummary"]["from_time"])
    to_timestamp = Timestamp(result.data["DiffTreeSummary"]["to_time"])
    summary = DiffSummaryCounters(
        num_added=diff["num_added"],
        num_updated=diff["num_updated"],
        num_unchanged=diff["num_unchanged"],
        num_removed=diff["num_removed"],
        num_conflicts=diff["num_conflicts"],
        from_time=from_timestamp,
        to_time=to_timestamp,
    )
    assert summary == counters
    assert result.data["DiffTreeSummary"]["num_untracked_base_changes"] == 0
    assert result.data["DiffTreeSummary"]["num_untracked_diff_changes"] == 0


@pytest.mark.parametrize(
    "filters,labels",
    [
        pytest.param({}, ["THING1", "thing2", "europe", "paris", "paris rack2", "paris-r1", "thing3"], id="no-filters"),
        pytest.param({"kind": {"includes": ["TestThing"]}}, ["THING1", "thing2", "thing3"], id="kind-includes"),
        pytest.param(
            {"kind": {"excludes": ["TestThing"]}}, ["europe", "paris", "paris rack2", "paris-r1"], id="kind-excludes"
        ),
        pytest.param({"namespace": {"includes": ["Test"]}}, ["THING1", "thing2", "thing3"], id="namespace-includes"),
        pytest.param(
            {"namespace": {"excludes": ["Location"]}}, ["THING1", "thing2", "thing3"], id="namespace-excludes"
        ),
        pytest.param(
            {"status": {"includes": ["UPDATED"]}},
            ["THING1", "europe", "paris", "paris rack2", "paris-r1"],
            id="status-includes",
        ),
        pytest.param(
            {"status": {"excludes": ["UNCHANGED"]}},
            ["THING1", "thing2", "europe", "paris", "paris rack2", "paris-r1", "thing3"],
            id="status-excludes",
        ),
        pytest.param(
            {"kind": {"includes": ["TestThing"]}, "status": {"excludes": ["ADDED"]}},
            ["THING1", "thing2"],
            id="kind-includes-status-excludes",
        ),
    ],
)
async def test_diff_get_filters(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data, filters, labels
) -> None:
    rack1_main = hierarchical_location_data["paris-r1"]
    rack2_main = hierarchical_location_data["paris-r2"]

    thing1_main = await Node.init(db=db, schema="TestThing")
    await thing1_main.new(db=db, name="thing1", location=rack1_main)
    await thing1_main.save(db=db)

    thing2_main = await Node.init(db=db, schema="TestThing")
    await thing2_main.new(db=db, name="thing2", location=rack2_main)
    await thing2_main.save(db=db)

    diff_branch = await create_branch(db=db, branch_name="diff")

    thing3_branch = await Node.init(db=db, schema="TestThing", branch=diff_branch)
    await thing3_branch.new(db=db, name="thing3", location=rack1_main)
    await thing3_branch.save(db=db)

    rack1_branch = await NodeManager.get_one(db=db, id=rack1_main.id, branch=diff_branch)
    rack1_branch.status.value = "offline"
    rack2_branch = await NodeManager.get_one(db=db, id=rack2_main.id, branch=diff_branch)
    rack2_branch.name.value = "paris rack2"

    await rack1_branch.save(db=db)
    await rack2_branch.save(db=db)

    thing1_branch = await NodeManager.get_one(db=db, id=thing1_main.id, branch=diff_branch)
    thing1_branch.name.value = "THING1"
    await thing1_branch.save(db=db)

    thing2_branch = await NodeManager.get_one(db=db, id=thing2_main.id, branch=diff_branch)
    await thing2_branch.delete(db=db)

    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=diff_branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch)
    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)

    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_FILTERS,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name, "filters": filters},
    )

    assert result.errors is None
    assert {node["label"] for node in result.data["DiffTree"]["nodes"]} == set(labels)


async def test_diff_tree_and_summary_filter_by_proposed_change_id(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema: NodeSchema,
    criticality_low,
    diff_branch: Branch,
    diff_coordinator: DiffCoordinator,
    diff_repository: DiffRepository,
) -> None:
    """Test that DiffTreeQuery and DiffTreeSummaryQuery filter results by proposed_change_id."""
    # Create a proposed change node
    proposed_change_id = str(uuid4())
    await db.execute_query(query="CREATE (pc:Node {uuid: $uuid})", params={"uuid": proposed_change_id})
    other_proposed_change_id = str(uuid4())
    await db.execute_query(query="CREATE (pc:Node {uuid: $uuid})", params={"uuid": other_proposed_change_id})

    # Make a change on the branch
    branch_crit = await NodeManager.get_one(db=db, id=criticality_low.id, branch=diff_branch)
    branch_crit.color.value = "#abcdef"
    await branch_crit.save(db=db)

    # Create the diff
    enriched_diff_metadata = await diff_coordinator.update_branch_diff(
        base_branch=default_branch, diff_branch=diff_branch
    )

    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)

    # -------------------------------------------------------------------------
    # DiffTree tests
    # -------------------------------------------------------------------------

    # Query without proposed_change_id filter - should return results
    result_without_filter = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_BY_PROPOSED_CHANGE,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )
    assert result_without_filter.errors is None
    assert result_without_filter.data["DiffTree"] is not None
    assert len(result_without_filter.data["DiffTree"]["nodes"]) == 1

    # Query with proposed_change_id filter (not linked yet) - should return None
    result_with_unlinked_filter = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_BY_PROPOSED_CHANGE,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name, "proposed_change_id": proposed_change_id},
    )
    assert result_with_unlinked_filter.errors is None
    assert result_with_unlinked_filter.data["DiffTree"] is None

    # -------------------------------------------------------------------------
    # DiffTreeSummary tests (before linking)
    # -------------------------------------------------------------------------

    # Query without proposed_change_id filter - should return results
    summary_without_filter = await graphql(
        schema=params.schema,
        source=DIFF_TREE_SUMMARY_QUERY_BY_PROPOSED_CHANGE,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )
    assert summary_without_filter.errors is None
    assert summary_without_filter.data["DiffTreeSummary"] is not None
    assert summary_without_filter.data["DiffTreeSummary"]["num_updated"] == 1

    # Query with proposed_change_id filter (not linked yet) - should return None
    summary_with_unlinked_filter = await graphql(
        schema=params.schema,
        source=DIFF_TREE_SUMMARY_QUERY_BY_PROPOSED_CHANGE,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name, "proposed_change_id": proposed_change_id},
    )
    assert summary_with_unlinked_filter.errors is None
    assert summary_with_unlinked_filter.data["DiffTreeSummary"] is None

    # -------------------------------------------------------------------------
    # Link the diff to the proposed change
    # -------------------------------------------------------------------------
    await diff_repository.link_to_proposed_change(
        diff_uuids=[enriched_diff_metadata.uuid],
        proposed_change_id=proposed_change_id,
    )

    # -------------------------------------------------------------------------
    # DiffTree tests (after linking)
    # -------------------------------------------------------------------------

    # Query with proposed_change_id filter (now linked) - should return results
    result_with_linked_filter = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_BY_PROPOSED_CHANGE,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name, "proposed_change_id": proposed_change_id},
    )
    assert result_with_linked_filter.errors is None
    assert result_with_linked_filter.data["DiffTree"] is not None
    assert len(result_with_linked_filter.data["DiffTree"]["nodes"]) == 1
    assert result_with_linked_filter.data["DiffTree"]["nodes"][0]["uuid"] == criticality_low.id

    # Query with a different proposed_change_id - should return None
    result_with_other_filter = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_BY_PROPOSED_CHANGE,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name, "proposed_change_id": other_proposed_change_id},
    )
    assert result_with_other_filter.errors is None
    assert result_with_other_filter.data["DiffTree"] is None

    # -------------------------------------------------------------------------
    # DiffTreeSummary tests (after linking)
    # -------------------------------------------------------------------------

    # Query with proposed_change_id filter (now linked) - should return results
    summary_with_linked_filter = await graphql(
        schema=params.schema,
        source=DIFF_TREE_SUMMARY_QUERY_BY_PROPOSED_CHANGE,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name, "proposed_change_id": proposed_change_id},
    )
    assert summary_with_linked_filter.errors is None
    assert summary_with_linked_filter.data["DiffTreeSummary"] is not None
    assert summary_with_linked_filter.data["DiffTreeSummary"]["num_updated"] == 1
    assert summary_with_linked_filter.data["DiffTreeSummary"]["base_branch"] == default_branch.name
    assert summary_with_linked_filter.data["DiffTreeSummary"]["diff_branch"] == diff_branch.name

    # Query with a different proposed_change_id - should return None
    summary_with_other_filter = await graphql(
        schema=params.schema,
        source=DIFF_TREE_SUMMARY_QUERY_BY_PROPOSED_CHANGE,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name, "proposed_change_id": other_proposed_change_id},
    )
    assert summary_with_other_filter.errors is None
    assert summary_with_other_filter.data["DiffTreeSummary"] is None


async def test_diff_tree_multiple_diffs_with_proposed_change_filter(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema: NodeSchema,
    criticality_low,
    diff_branch: Branch,
    diff_coordinator: DiffCoordinator,
    diff_repository: DiffRepository,
) -> None:
    """Test DiffTreeQuery filtering with multiple diffs for the same branch.

    This test simulates a legacy merge scenario that is not possible as of 1.8.0:
    - time0: branch is created (original branched_from)
    - Changes are made on the branch
    - diff1 is created covering time0 to just before time1
    - time1: branch is merged (branched_from is updated to time1)
    - More changes are made on the branch
    - diff2 is created covering time1 to time2 (now)

    Each diff is linked to a different proposed change, and we validate:
    1. Filter by just branch name returns the latest diff (diff2)
    2. Filter by branch name and proposed_change_id returns the correct diff
    3. Filter by branch name and time range returns the correct diff
    4. Filter by branch name, time range, and proposed_change_id returns the correct diff
    """
    # Create proposed change nodes
    proposed_change_1_id = str(uuid4())
    proposed_change_2_id = str(uuid4())
    await db.execute_query(query="CREATE (pc:Node {uuid: $uuid})", params={"uuid": proposed_change_1_id})
    await db.execute_query(query="CREATE (pc:Node {uuid: $uuid})", params={"uuid": proposed_change_2_id})

    # Record time0 (original branched_from time when branch was created)
    time0 = Timestamp(diff_branch.branched_from)

    # Make first change on the branch
    branch_crit = await NodeManager.get_one(db=db, id=criticality_low.id, branch=diff_branch)
    branch_crit.color.value = "#111111"
    await branch_crit.save(db=db)

    # Record time1 (this will be the new branched_from after merge/rebase)
    time1 = Timestamp()

    # Create diff1: from time0 to just before time1 (covers first change, before merge)
    diff1_metadata = await diff_coordinator.create_or_update_arbitrary_timeframe_diff(
        base_branch=default_branch,
        diff_branch=diff_branch,
        from_time=time0,
        to_time=time1,
        name="diff1",
    )

    # Link diff1 to proposed_change_1
    await diff_repository.link_to_proposed_change(
        diff_uuids=[diff1_metadata.uuid, diff1_metadata.partner_uuid],
        proposed_change_id=proposed_change_1_id,
    )

    # Simulate merge by updating the branch's branched_from to time1
    diff_branch.branched_from = time1.to_string()
    await diff_branch.save(db=db)

    # Make second change on the branch (after merge)
    branch_crit = await NodeManager.get_one(db=db, id=criticality_low.id, branch=diff_branch)
    branch_crit.color.value = "#222222"
    await branch_crit.save(db=db)

    # Record time2 (after second change, which is now)
    time2 = Timestamp()

    # Create diff2: from time1 (new branched_from) to time2 (covers second change, after merge)
    diff2_metadata = await diff_coordinator.create_or_update_arbitrary_timeframe_diff(
        base_branch=default_branch,
        diff_branch=diff_branch,
        from_time=time1,
        to_time=time2,
        name="diff2",
    )

    # Link diff2 to proposed_change_2
    await diff_repository.link_to_proposed_change(
        diff_uuids=[diff2_metadata.uuid, diff2_metadata.partner_uuid],
        proposed_change_id=proposed_change_2_id,
    )

    default_branch.update_schema_hash()
    params = await prepare_graphql_params(db=db, branch=default_branch)

    # -------------------------------------------------------------------------
    # Test 1: Filter by just branch name - should return the latest diff (diff2)
    # -------------------------------------------------------------------------
    result_branch_only = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_ALL_FILTERS,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )
    assert result_branch_only.errors is None
    assert result_branch_only.data["DiffTree"] is not None
    # When querying without proposed_change_id, the default time range is branched_from to now
    assert len(result_branch_only.data["DiffTree"]["nodes"]) == 1
    assert result_branch_only.data["DiffTree"]["name"] == "diff2"

    # -------------------------------------------------------------------------
    # Test 2: Filter by branch name and proposed_change_1 - should return diff1
    # -------------------------------------------------------------------------
    result_pc1 = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_ALL_FILTERS,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name, "proposed_change_id": proposed_change_1_id},
    )
    assert result_pc1.errors is None
    assert result_pc1.data["DiffTree"] is not None
    # Verify this is diff1 by checking the time range
    assert result_pc1.data["DiffTree"]["from_time"] == time0.to_datetime().isoformat()
    assert result_pc1.data["DiffTree"]["to_time"] == time1.to_datetime().isoformat()
    assert result_pc1.data["DiffTree"]["name"] == "diff1"
    assert len(result_pc1.data["DiffTree"]["nodes"]) == 1
    assert result_pc1.data["DiffTree"]["nodes"][0]["uuid"] == criticality_low.id

    # -------------------------------------------------------------------------
    # Test 3: Filter by branch name and proposed_change_2 - should return diff2
    # -------------------------------------------------------------------------
    result_pc2 = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_ALL_FILTERS,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name, "proposed_change_id": proposed_change_2_id},
    )
    assert result_pc2.errors is None
    assert result_pc2.data["DiffTree"] is not None
    # Verify this is diff2 by checking the time range
    assert result_pc2.data["DiffTree"]["from_time"] == time1.to_datetime().isoformat()
    assert result_pc2.data["DiffTree"]["to_time"] == time2.to_datetime().isoformat()
    assert result_pc2.data["DiffTree"]["name"] == "diff2"
    assert len(result_pc2.data["DiffTree"]["nodes"]) == 1
    assert result_pc2.data["DiffTree"]["nodes"][0]["uuid"] == criticality_low.id

    # -------------------------------------------------------------------------
    # Test 4: Filter by branch name and time range covering diff1 - should return diff1
    # -------------------------------------------------------------------------
    result_time_range_1 = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_ALL_FILTERS,
        context_value=params.context,
        root_value=None,
        variable_values={
            "branch": diff_branch.name,
            "from_time": time0.to_datetime().isoformat(),
            "to_time": time1.to_datetime().isoformat(),
        },
    )
    assert result_time_range_1.errors is None
    assert result_time_range_1.data["DiffTree"] is not None
    # Verify this is diff1 by checking the time range
    assert result_time_range_1.data["DiffTree"]["from_time"] == time0.to_datetime().isoformat()
    assert result_time_range_1.data["DiffTree"]["to_time"] == time1.to_datetime().isoformat()
    assert result_time_range_1.data["DiffTree"]["name"] == "diff1"

    # -------------------------------------------------------------------------
    # Test 5: Filter by branch name and time range covering diff2 - should return diff2
    # -------------------------------------------------------------------------
    result_time_range_2 = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_ALL_FILTERS,
        context_value=params.context,
        root_value=None,
        variable_values={
            "branch": diff_branch.name,
            "from_time": time1.to_datetime().isoformat(),
            "to_time": time2.to_datetime().isoformat(),
        },
    )
    assert result_time_range_2.errors is None
    assert result_time_range_2.data["DiffTree"] is not None
    # Verify this is diff2 by checking the time range
    assert result_time_range_2.data["DiffTree"]["from_time"] == time1.to_datetime().isoformat()
    assert result_time_range_2.data["DiffTree"]["to_time"] == time2.to_datetime().isoformat()
    assert result_time_range_2.data["DiffTree"]["name"] == "diff2"

    # -------------------------------------------------------------------------
    # Test 6: Filter by branch name, time range, and proposed_change_1 - should return diff1
    # -------------------------------------------------------------------------
    result_time_range_pc1 = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_ALL_FILTERS,
        context_value=params.context,
        root_value=None,
        variable_values={
            "branch": diff_branch.name,
            "from_time": time0.to_datetime().isoformat(),
            "to_time": time1.to_datetime().isoformat(),
            "proposed_change_id": proposed_change_1_id,
        },
    )
    assert result_time_range_pc1.errors is None
    assert result_time_range_pc1.data["DiffTree"] is not None
    # Verify this is diff1 by checking the time range
    assert result_time_range_pc1.data["DiffTree"]["from_time"] == time0.to_datetime().isoformat()
    assert result_time_range_pc1.data["DiffTree"]["to_time"] == time1.to_datetime().isoformat()
    assert result_time_range_pc1.data["DiffTree"]["name"] == "diff1"

    # -------------------------------------------------------------------------
    # Test 7: Filter by branch name, time range, and proposed_change_2 - should return diff2
    # -------------------------------------------------------------------------
    result_time_range_pc2 = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_ALL_FILTERS,
        context_value=params.context,
        root_value=None,
        variable_values={
            "branch": diff_branch.name,
            "from_time": time1.to_datetime().isoformat(),
            "to_time": time2.to_datetime().isoformat(),
            "proposed_change_id": proposed_change_2_id,
        },
    )
    assert result_time_range_pc2.errors is None
    assert result_time_range_pc2.data["DiffTree"] is not None
    # Verify this is diff2 by checking the time range
    assert result_time_range_pc2.data["DiffTree"]["from_time"] == time1.to_datetime().isoformat()
    assert result_time_range_pc2.data["DiffTree"]["to_time"] == time2.to_datetime().isoformat()
    assert result_time_range_pc2.data["DiffTree"]["name"] == "diff2"

    # -------------------------------------------------------------------------
    # Test 8: Filter by wrong combination - diff1 time range with proposed_change_2 - should return None
    # -------------------------------------------------------------------------
    result_mismatch = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_ALL_FILTERS,
        context_value=params.context,
        root_value=None,
        variable_values={
            "branch": diff_branch.name,
            "from_time": time0.to_datetime().isoformat(),
            "to_time": time1.to_datetime().isoformat(),
            "proposed_change_id": proposed_change_2_id,
        },
    )
    assert result_mismatch.errors is None
    # This should return None because diff2 doesn't match the time range of diff1
    assert result_mismatch.data["DiffTree"] is None
