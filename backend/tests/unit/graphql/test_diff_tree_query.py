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
                "label": "",
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

    #         {
    #             "uuid": "cdea5cb3-36eb-4b26-87aa-0a1123dd7960",
    #             "kind": "SomethingKind",
    #             "label": "SomethingLabel",
    #             "last_changed_at": "2024-02-03T04:05:06+00:00",
    #             "num_added": 1,
    #             "num_removed": 0,
    #             "num_updated": 0,
    #             "num_conflicts": 0,
    #             "status": "ADDED",
    #             "contains_conflict": False,
    #             "relationships": [],
    #             "attributes": [
    #                 {
    #                     "name": "SomethingAttribute",
    #                     "last_changed_at": "2024-02-03T04:05:06+00:00",
    #                     "num_added": 1,
    #                     "num_removed": 0,
    #                     "num_updated": 0,
    #                     "num_conflicts": 0,
    #                     "status": "ADDED",
    #                     "contains_conflict": False,
    #                     "properties": [
    #                         {
    #                             "property_type": "value",
    #                             "last_changed_at": "2024-02-03T04:05:06+00:00",
    #                             "previous_value": None,
    #                             "new_value": "42",
    #                             "status": "ADDED",
    #                             "conflict": None,
    #                         }
    #                     ],
    #                 }
    #             ],
    #         },
    #         {
    #             "uuid": "990e1eda-687b-454d-a6c3-dc6039f125dd",
    #             "kind": "ChildKind",
    #             "label": "ChildLabel",
    #             "last_changed_at": "2024-02-03T04:05:06+00:00",
    #             "status": "UPDATED",
    #             "contains_conflict": False,
    #             "num_added": 0,
    #             "num_removed": 0,
    #             "num_updated": 1,
    #             "num_conflicts": 0,
    #             "relationships": [],
    #             "attributes": [
    #                 {
    #                     "name": "ChildAttribute",
    #                     "last_changed_at": "2024-02-03T04:05:06+00:00",
    #                     "num_added": 0,
    #                     "num_removed": 0,
    #                     "num_updated": 1,
    #                     "num_conflicts": 0,
    #                     "status": "UPDATED",
    #                     "contains_conflict": False,
    #                     "properties": [
    #                         {
    #                             "property_type": "owner",
    #                             "last_changed_at": "2024-02-03T04:05:06+00:00",
    #                             "previous_value": "herbert",
    #                             "new_value": "willy",
    #                             "status": "UPDATED",
    #                             "conflict": None,
    #                         }
    #                     ],
    #                 }
    #             ],
    #         },
    #         {
    #             "uuid": "2beecc03-8d17-4360-b331-f242c9fb4997",
    #             "kind": "ParentKind",
    #             "num_added": 0,
    #             "num_updated": 0,
    #             "num_removed": 0,
    #             "num_conflicts": 0,
    #             "last_changed_at": "2024-02-03T04:05:06+00:00",
    #             "label": "ParentLabel",
    #             "status": "UNCHANGED",
    #             "contains_conflict": False,
    #             "attributes": [],
    #             "relationships": [
    #                 {
    #                     "name": "child_relationship",
    #                     "last_changed_at": "2024-02-03T04:05:06+00:00",
    #                     "status": "UPDATED",
    #                     "contains_conflict": False,
    #                     "elements": [],
    #                     "node_uuids": ["990e1eda-687b-454d-a6c3-dc6039f125dd"],
    #                 }
    #             ],
    #         },
    #         {
    #             "uuid": "a1b2f0c8-eda7-47e3-b3a2-5a055974c19c",
    #             "kind": "RelationshipConflictKind",
    #             "num_added": 0,
    #             "num_updated": 1,
    #             "num_removed": 0,
    #             "num_conflicts": 1,
    #             "last_changed_at": "2024-02-03T04:05:06+00:00",
    #             "label": "RelationshipConflictLabel",
    #             "status": "UPDATED",
    #             "contains_conflict": True,
    #             "attributes": [],
    #             "relationships": [
    #                 {
    #                     "name": "conflict_relationship",
    #                     "last_changed_at": "2024-02-03T04:05:06+00:00",
    #                     "status": "UPDATED",
    #                     "contains_conflict": True,
    #                     "node_uuids": [],
    #                     "elements": [
    #                         {
    #                             "last_changed_at": "2024-02-03T04:05:06+00:00",
    #                             "status": "UPDATED",
    #                             "peer_id": "7f0d1a04-1543-4d7e-b348-8fb1d19f7a8c",
    #                             "contains_conflict": True,
    #                             "conflict": None,
    #                             "properties": [
    #                                 {
    #                                     "property_type": "peer_id",
    #                                     "last_changed_at": "2024-02-03T04:05:06+00:00",
    #                                     "previous_value": "87a4e7f8-5d7d-4b22-ab92-92b4d8890e75",
    #                                     "new_value": "c411c56f-d88b-402d-8753-0a35defaab1f",
    #                                     "status": "UPDATED",
    #                                     "conflict": {
    #                                         "uuid": "0a7a5898-e8a0-4baf-b7ae-1fac1fcdf468",
    #                                         "base_branch_action": "REMOVED",
    #                                         "base_branch_value": None,
    #                                         "base_branch_changed_at": "2024-02-03T04:05:06+00:00",
    #                                         "diff_branch_action": "UPDATED",
    #                                         "diff_branch_value": "c411c56f-d88b-402d-8753-0a35defaab1f",
    #                                         "diff_branch_changed_at": "2024-02-03T04:05:06+00:00",
    #                                         "selected_branch": None,
    #                                     },
    #                                 },
    #                                 {
    #                                     "property_type": "is_visible",
    #                                     "last_changed_at": "2024-02-03T04:05:06+00:00",
    #                                     "previous_value": "false",
    #                                     "new_value": "true",
    #                                     "status": "UPDATED",
    #                                     "conflict": {
    #                                         "uuid": "60b2456b-0dcd-47c9-a9f1-590b30a597de",
    #                                         "base_branch_action": "REMOVED",
    #                                         "base_branch_value": None,
    #                                         "base_branch_changed_at": "2024-02-03T04:05:06+00:00",
    #                                         "diff_branch_action": "UPDATED",
    #                                         "diff_branch_value": "true",
    #                                         "diff_branch_changed_at": "2024-02-03T04:05:06+00:00",
    #                                         "selected_branch": "DIFF_BRANCH",
    #                                     },
    #                                 },
    #                             ],
    #                         }
    #                     ],
    #                 }
    #             ],
    #         },
    #     ],
    # }
