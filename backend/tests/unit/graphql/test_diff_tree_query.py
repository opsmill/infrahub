from datetime import UTC, datetime

import pytest
from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.query.diff_summary import DiffSummaryCounters
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from infrahub.graphql import prepare_graphql_params

ADDED_ACTION = "ADDED"
UPDATED_ACTION = "UPDATED"
REMOVED_ACTION = "REMOVED"
UNCHANGED_ACTION = "UNCHANGED"

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
                properties {
                    property_type
                    last_changed_at
                    previous_value
                    new_value
                    status
                    conflict {
                        uuid
                        base_branch_action
                        base_branch_value
                        base_branch_changed_at
                        diff_branch_action
                        diff_branch_value
                        diff_branch_changed_at
                        selected_branch
                    }
                }
            }
            relationships {
                name
                last_changed_at
                status
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
                        diff_branch_action
                        diff_branch_value
                        diff_branch_changed_at
                        selected_branch
                    }
                    properties {
                        property_type
                        last_changed_at
                        previous_value
                        new_value
                        status
                        conflict {
                            uuid
                            base_branch_action
                            base_branch_value
                            base_branch_changed_at
                            diff_branch_action
                            diff_branch_value
                            diff_branch_changed_at
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
    }
}
"""


async def test_diff_tree_empty_diff(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema):
    diff_branch = await create_branch(db=db, branch_name="diff")

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
    db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema, criticality_low
):
    diff_branch = await create_branch(db=db, branch_name="diff")
    branch_crit = await NodeManager.get_one(db=db, id=criticality_low.id, branch=diff_branch)
    branch_crit.color.value = "#abcdef"
    before_change_datetime = datetime.now(tz=UTC)
    await branch_crit.save(db=db)
    after_change_datetime = datetime.now(tz=UTC)

    params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name},
    )
    from_time = datetime.fromisoformat(diff_branch.created_at)
    to_time = datetime.fromisoformat(params.context.at.to_string())

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
        "num_conflicts": 0,
        "nodes": [
            {
                "uuid": criticality_low.id,
                "kind": criticality_low.get_kind(),
                "label": "Low",
                "last_changed_at": node_changed_at,
                "num_added": 0,
                "num_removed": 0,
                "num_updated": 1,
                "parent": None,
                "num_conflicts": 0,
                "status": UPDATED_ACTION,
                "contains_conflict": False,
                "relationships": [],
                "attributes": [
                    {
                        "name": "color",
                        "last_changed_at": attribute_changed_at,
                        "num_added": 0,
                        "num_removed": 0,
                        "num_updated": 1,
                        "num_conflicts": 0,
                        "status": UPDATED_ACTION,
                        "contains_conflict": False,
                        "properties": [
                            {
                                "property_type": "HAS_VALUE",
                                "last_changed_at": property_changed_at,
                                "previous_value": criticality_low.color.value,
                                "new_value": branch_crit.color.value,
                                "status": UPDATED_ACTION,
                                "conflict": None,
                            }
                        ],
                    }
                ],
            }
        ],
    }


async def test_diff_tree_hierarchy_change(db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data):
    diff_branch = await create_branch(db=db, branch_name="diff")

    europe_main = hierarchical_location_data["europe"]
    paris_main = hierarchical_location_data["paris"]
    rack1_main = hierarchical_location_data["paris-r1"]
    rack1_main = hierarchical_location_data["paris-r1"]
    rack2_main = hierarchical_location_data["paris-r2"]

    # rprint(hierarchical_location_data)
    rack1_branch = await NodeManager.get_one(db=db, id=rack1_main.id, branch=diff_branch)
    rack1_branch.status.value = "offline"
    rack2_branch = await NodeManager.get_one(db=db, id=rack2_main.id, branch=diff_branch)
    rack2_branch.name.value = "paris rack2"

    await rack1_branch.save(db=db)
    await rack2_branch.save(db=db)

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


@pytest.mark.parametrize(
    "filters,counters",
    [
        pytest.param({}, DiffSummaryCounters(num_added=2, num_updated=4), id="no-filters"),
        pytest.param(
            {"kind": {"includes": ["TestThing"]}}, DiffSummaryCounters(num_added=2, num_updated=1), id="kind-includes"
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

    # rprint(hierarchical_location_data)
    rack1_branch = await NodeManager.get_one(db=db, id=rack1_main.id, branch=diff_branch)
    rack1_branch.status.value = "offline"
    rack2_branch = await NodeManager.get_one(db=db, id=rack2_main.id, branch=diff_branch)
    rack2_branch.name.value = "paris rack2"

    await rack1_branch.save(db=db)
    await rack2_branch.save(db=db)

    thing1_branch = await NodeManager.get_one(db=db, id=thing1_main.id, branch=diff_branch)
    thing1_branch.name.value = "THING1"
    await thing1_branch.save(db=db)

    # FIXME, there is an issue related to label for deleted nodes right now that makes it complicated to use REMOVED nodes in this test
    # thing2_branch = await NodeManager.get_one(db=db, id=thing2_main.id, branch=diff_branch)
    # await thing2_branch.delete(db=db)

    # ----------------------------
    # Generate Diff in DB
    # ----------------------------
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=diff_branch)

    from_timestamp = Timestamp(diff_branch.get_created_at())
    to_timestamp = Timestamp()

    await diff_coordinator.update_diffs(
        base_branch=default_branch,
        diff_branch=diff_branch,
        from_time=from_timestamp,
        to_time=to_timestamp,
    )

    params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=default_branch)

    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_SUMMARY,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name, "filters": filters},
    )

    assert result.errors is None
    diff: dict = result.data["DiffTreeSummary"]
    summary = DiffSummaryCounters(
        num_added=diff["num_added"],
        num_updated=diff["num_updated"],
        num_unchanged=diff["num_unchanged"],
        num_removed=diff["num_removed"],
        num_conflicts=diff["num_conflicts"],
    )
    assert summary == counters


@pytest.mark.parametrize(
    "filters,labels",
    [
        pytest.param({}, ["THING1", "europe", "paris", "paris rack2", "paris-r1", "thing3"], id="no-filters"),
        pytest.param({"kind": {"includes": ["TestThing"]}}, ["THING1", "thing3"], id="kind-includes"),
        pytest.param(
            {"kind": {"excludes": ["TestThing"]}}, ["europe", "paris", "paris rack2", "paris-r1"], id="kind-excludes"
        ),
        pytest.param({"namespace": {"includes": ["Test"]}}, ["THING1", "thing3"], id="namespace-includes"),
        pytest.param({"namespace": {"excludes": ["Location"]}}, ["THING1", "thing3"], id="namespace-excludes"),
        pytest.param(
            {"status": {"includes": ["UPDATED"]}},
            ["THING1", "europe", "paris", "paris rack2", "paris-r1"],
            id="status-includes",
        ),
        pytest.param(
            {"status": {"excludes": ["UNCHANGED"]}},
            ["THING1", "europe", "paris", "paris rack2", "paris-r1", "thing3"],
            id="status-excludes",
        ),
        pytest.param(
            {"kind": {"includes": ["TestThing"]}, "status": {"excludes": ["ADDED"]}},
            ["THING1"],
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

    # rprint(hierarchical_location_data)
    rack1_branch = await NodeManager.get_one(db=db, id=rack1_main.id, branch=diff_branch)
    rack1_branch.status.value = "offline"
    rack2_branch = await NodeManager.get_one(db=db, id=rack2_main.id, branch=diff_branch)
    rack2_branch.name.value = "paris rack2"

    await rack1_branch.save(db=db)
    await rack2_branch.save(db=db)

    thing1_branch = await NodeManager.get_one(db=db, id=thing1_main.id, branch=diff_branch)
    thing1_branch.name.value = "THING1"
    await thing1_branch.save(db=db)

    # FIXME, there is an issue related to label for deleted nodes right now that makes it complicated to use REMOVED nodes in this test
    # thing2_branch = await NodeManager.get_one(db=db, id=thing2_main.id, branch=diff_branch)
    # await thing2_branch.delete(db=db)

    params = prepare_graphql_params(db=db, include_mutation=False, include_subscription=False, branch=default_branch)

    result = await graphql(
        schema=params.schema,
        source=DIFF_TREE_QUERY_FILTERS,
        context_value=params.context,
        root_value=None,
        variable_values={"branch": diff_branch.name, "filters": filters},
    )

    assert result.errors is None
    # breakpoint()
    assert set([node["label"] for node in result.data["DiffTree"]["nodes"]]) == set(labels)
