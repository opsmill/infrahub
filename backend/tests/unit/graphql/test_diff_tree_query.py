from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from graphql import graphql

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

ADDED_ACTION = "ADDED"
UPDATED_ACTION = "UPDATED"
REMOVED_ACTION = "REMOVED"
UNCHANGED_ACTION = "UNCHANGED"
CARDINALITY_ONE = "ONE"
CARDINALITY_MANY = "MANY"
IS_RELATED_TYPE = "IS_RELATED"
IS_PROTECTED_TYPE = "IS_PROTECTED"
IS_VISIBLE_TYPE = "IS_VISIBLE"

DIFF_TREE_QUERY = """
query GetDiffTree($branch: String){
    DiffTree (branch: $branch) {
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
):
    enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch)
    from_time = datetime.fromisoformat(diff_branch.branched_from)
    to_time = datetime.fromisoformat(enriched_diff.to_time.to_string())

    params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )

    assert result.errors is None
    assert result.data["DiffTree"] == {
        "base_branch": default_branch.name,
        "diff_branch": diff_branch.name,
        "from_time": from_time.isoformat(),
        "to_time": to_time.isoformat(),
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
):
    params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )

    assert result.errors is None
    assert result.data["DiffTree"] is None


async def test_diff_tree_no_branch(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema):
    params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=default_branch)
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
):
    main_crit = await NodeManager.get_one(db=db, id=criticality_low.id, branch=default_branch)
    main_crit.color.value = "#fedcba"
    branch_crit = await NodeManager.get_one(db=db, id=criticality_low.id, branch=diff_branch)
    branch_crit.color.value = "#abcdef"
    before_change_datetime = datetime.now(tz=UTC)
    await main_crit.save(db=db)
    await branch_crit.save(db=db)
    after_change_datetime = datetime.now(tz=UTC)

    enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch)
    enriched_conflict = enriched_diff.get_all_conflicts()[0]
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

    params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )
    from_time = datetime.fromisoformat(diff_branch.branched_from)
    to_time = datetime.fromisoformat(enriched_diff.to_time.to_string())

    assert result.errors is None

    assert result.data["DiffTree"]
    assert result.data["DiffTree"]["nodes"]
    node_diff = result.data["DiffTree"]["nodes"][0]
    node_changed_at = node_diff["last_changed_at"]
    assert datetime.fromisoformat(node_changed_at) < before_change_datetime
    assert node_diff["attributes"]
    attribute_diff = node_diff["attributes"][0]
    attribute_changed_at = attribute_diff["last_changed_at"]
    assert datetime.fromisoformat(attribute_changed_at) < before_change_datetime
    assert attribute_diff["properties"]
    property_diff = attribute_diff["properties"][0]
    property_changed_at = property_diff["last_changed_at"]
    assert before_change_datetime < datetime.fromisoformat(property_changed_at) < after_change_datetime
    assert result.data["DiffTree"] == {
        "base_branch": "main",
        "diff_branch": diff_branch.name,
        "from_time": from_time.isoformat(),
        "to_time": to_time.isoformat(),
        "num_added": 0,
        "num_removed": 0,
        "num_updated": 1,
        "num_conflicts": 1,
        "num_untracked_base_changes": 1,
        "num_untracked_diff_changes": 1,
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
):
    branch_car = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=diff_branch)
    await branch_car.owner.update(db=db, data=[person_jane_main])
    before_change_datetime = datetime.now(tz=UTC)
    await branch_car.save(db=db)
    after_change_datetime = datetime.now(tz=UTC)
    accord_label = await branch_car.render_display_label(db=db)
    john_label = await person_john_main.render_display_label(db=db)
    jane_label = await person_jane_main.render_display_label(db=db)

    enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch)
    params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )
    from_time = datetime.fromisoformat(diff_branch.branched_from)
    to_time = datetime.fromisoformat(enriched_diff.to_time.to_string())

    assert result.errors is None

    assert result.data["DiffTree"]
    diff_tree_response = result.data["DiffTree"].copy()
    nodes_response = diff_tree_response.pop("nodes")
    assert diff_tree_response == {
        "base_branch": "main",
        "diff_branch": diff_branch.name,
        "from_time": from_time.isoformat(),
        "to_time": to_time.isoformat(),
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
    assert datetime.fromisoformat(car_changed_at) < before_change_datetime
    assert car_response == {
        "uuid": car_accord_main.id,
        "kind": car_accord_main.get_kind(),
        "label": await car_accord_main.render_display_label(db=db),
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
    assert before_change_datetime < datetime.fromisoformat(owner_changed_at) < after_change_datetime
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
    assert before_change_datetime < datetime.fromisoformat(owner_element_changed_at) < after_change_datetime
    owner_properties = owner_element.pop("properties")
    assert owner_element == {
        "status": UPDATED_ACTION,
        "peer_id": person_jane_main.id,
        "last_changed_at": owner_element_changed_at,
        "contains_conflict": False,
        "conflict": None,
    }
    owner_properties_by_type = {p["property_type"]: p for p in owner_properties}
    assert set(owner_properties_by_type.keys()) == {IS_RELATED_TYPE}
    owner_prop = owner_properties_by_type[IS_RELATED_TYPE]
    owner_prop_changed_at = owner_prop["last_changed_at"]
    assert before_change_datetime < datetime.fromisoformat(owner_prop_changed_at) < after_change_datetime
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
    assert datetime.fromisoformat(john_changed_at) < before_change_datetime
    assert john_response == {
        "uuid": person_john_main.id,
        "kind": person_john_main.get_kind(),
        "label": await person_john_main.render_display_label(db=db),
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
    assert before_change_datetime < datetime.fromisoformat(cars_changed_at) < after_change_datetime
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
    assert before_change_datetime < datetime.fromisoformat(cars_element_changed_at) < after_change_datetime
    cars_properties = cars_element.pop("properties")
    assert cars_element == {
        "status": REMOVED_ACTION,
        "peer_id": car_accord_main.id,
        "last_changed_at": cars_element_changed_at,
        "contains_conflict": False,
        "conflict": None,
    }
    cars_properties_by_type = {p["property_type"]: p for p in cars_properties}
    assert set(cars_properties_by_type.keys()) == {IS_RELATED_TYPE, IS_VISIBLE_TYPE, IS_PROTECTED_TYPE}
    for property_type, previous_value, previous_label in [
        (IS_RELATED_TYPE, car_accord_main.id, accord_label),
        (IS_PROTECTED_TYPE, "False", None),
        (IS_VISIBLE_TYPE, "True", None),
    ]:
        cars_prop = cars_properties_by_type[property_type]
        cars_prop_changed_at = cars_prop["last_changed_at"]
        assert before_change_datetime < datetime.fromisoformat(cars_prop_changed_at) < after_change_datetime
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
    assert datetime.fromisoformat(jane_changed_at) < before_change_datetime
    assert jane_response == {
        "uuid": person_jane_main.id,
        "kind": person_jane_main.get_kind(),
        "label": await person_jane_main.render_display_label(db=db),
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
    assert before_change_datetime < datetime.fromisoformat(cars_changed_at) < after_change_datetime
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
    assert before_change_datetime < datetime.fromisoformat(cars_element_changed_at) < after_change_datetime
    cars_properties = cars_element.pop("properties")
    assert cars_element == {
        "status": ADDED_ACTION,
        "peer_id": car_accord_main.id,
        "last_changed_at": cars_element_changed_at,
        "contains_conflict": False,
        "conflict": None,
    }
    cars_properties_by_type = {p["property_type"]: p for p in cars_properties}
    assert set(cars_properties_by_type.keys()) == {IS_RELATED_TYPE, IS_VISIBLE_TYPE, IS_PROTECTED_TYPE}
    for property_type, new_value, new_label in [
        (IS_RELATED_TYPE, car_accord_main.id, accord_label),
        (IS_PROTECTED_TYPE, "False", None),
        (IS_VISIBLE_TYPE, "True", None),
    ]:
        cars_prop = cars_properties_by_type[property_type]
        cars_prop_changed_at = cars_prop["last_changed_at"]
        assert before_change_datetime < datetime.fromisoformat(cars_prop_changed_at) < after_change_datetime
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
):
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
    params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )

    assert result.errors is None
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
):
    params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_SUMMARY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )

    assert result.errors is None
    assert result.data["DiffTreeSummary"] is None


async def test_diff_tree_summary_no_changes(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_low,
    diff_coordinator: DiffCoordinator,
    diff_branch: Branch,
):
    enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch)
    from_time = datetime.fromisoformat(diff_branch.branched_from)
    to_time = datetime.fromisoformat(enriched_diff.to_time.to_string())

    params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_SUMMARY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )

    assert result.errors is None
    assert result.data["DiffTreeSummary"] == {
        "base_branch": default_branch.name,
        "diff_branch": diff_branch.name,
        "from_time": from_time.isoformat(),
        "to_time": to_time.isoformat(),
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
            DiffSummaryCounters(num_added=2, num_updated=5, num_removed=2, from_time=Timestamp(), to_time=Timestamp()),
            id="no-filters",
        ),
        pytest.param(
            {"kind": {"includes": ["TestThing"]}},
            DiffSummaryCounters(num_added=2, num_updated=1, num_removed=2, from_time=Timestamp(), to_time=Timestamp()),
            id="kind-includes",
        ),
    ],
)
async def test_diff_summary_filters(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data, filters, counters
):
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
    enriched_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=diff_branch)
    params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=default_branch)

    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_SUMMARY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name, "filters": filters},
    )

    assert result.errors is None
    counters.from_time = enriched_diff.from_time
    counters.to_time = enriched_diff.to_time
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
):
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
    params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=default_branch)

    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_FILTERS,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name, "filters": filters},
    )

    assert result.errors is None
    assert set([node["label"] for node in result.data["DiffTree"]["nodes"]]) == set(labels)
