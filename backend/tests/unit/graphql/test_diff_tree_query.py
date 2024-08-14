from datetime import UTC, datetime

from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
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
                node_uuids
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
    from_time = datetime.fromisoformat(diff_branch.created_at)
    to_time = datetime.fromisoformat(params.context.at.to_string())

    assert result.errors is None

    assert result.data["DiffTree"] == {
        "base_branch": "main",
        "diff_branch": "diff",
        "from_time": from_time.isoformat(),
        "to_time": to_time.isoformat(),
        "num_added": 0,
        "num_removed": 0,
        "num_updated": 0,
        "num_conflicts": 0,
        "nodes": [],
    }


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

    # rprint(hierarchical_location_data)
    rack1_main = hierarchical_location_data["paris-r1"]
    rack2_main = hierarchical_location_data["paris-r2"]
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
