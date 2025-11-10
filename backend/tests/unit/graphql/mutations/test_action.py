from uuid import uuid4

from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql


async def _prepare_group_action(
    db: InfrahubDatabase,
    default_branch: Branch,
) -> str:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    query = """
    mutation {
        CoreStandardGroupCreate(data: {
            name: { value: "group1"},
        })
        {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    query = """
    mutation {
        CoreGroupActionCreate(data: {
            name: { value: "group1-action1"},
            group: { id: "group1"}
        })
        {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    return result.data["CoreGroupActionCreate"]["object"]["id"]


async def test_create_node_trigger_failure_states(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, car_person_schema: None
) -> None:
    group_id = await _prepare_group_action(db=db, default_branch=default_branch)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_NODE_TRIGGER,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "trigger1", "node_kind": "InvalidNodeKind", "action": group_id},
    )

    assert result.errors
    assert "The requested node_kind schema was not found at node_kind" in str(result.errors)

    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_NODE_TRIGGER,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "trigger1", "node_kind": "CoreGenericRepository", "action": "group1-action1"},
    )

    assert result.errors
    assert "The requested node_kind is not a valid node" in str(result.errors)


async def test_modify_action_node_attribute_matches(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, car_person_schema: None
) -> None:
    group_id = await _prepare_group_action(db=db, default_branch=default_branch)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_NODE_TRIGGER,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "trigger1", "node_kind": "TestCar", "action": group_id},
    )
    assert not result.errors
    assert result.data
    trigger_id = result.data["CoreNodeTriggerRuleCreate"]["object"]["id"]

    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_NODE_TRIGGER_ATTRIBUTE_MATCH,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"attribute_name": "missing_attribute", "trigger": trigger_id, "value": "trigger-on-this"},
    )

    assert "The attribute missing_attribute doesn't exist on related node trigger using TestCar" in str(result.errors)

    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_NODE_TRIGGER_ATTRIBUTE_MATCH,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"attribute_name": "color", "trigger": trigger_id, "value": "trigger-on-this"},
    )
    assert not result.errors
    assert result.data
    attribute_match_id = result.data["CoreNodeTriggerAttributeMatchCreate"]["object"]["id"]

    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_NODE_TRIGGER_ATTRIBUTE_MATCH,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"attribute_name": "invalid_attribute_name", "id": attribute_match_id},
    )

    assert "The attribute invalid_attribute_name doesn't exist on related node trigger using TestCar" in str(
        result.errors
    )

    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_NODE_TRIGGER_ATTRIBUTE_MATCH,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"attribute_name": "name", "id": attribute_match_id},
    )
    assert not result.errors
    assert result.data


async def test_modify_action_node_relationship_matches(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, car_person_schema: None
) -> None:
    group_id = await _prepare_group_action(db=db, default_branch=default_branch)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_NODE_TRIGGER,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "trigger1", "node_kind": "TestCar", "action": group_id},
    )
    assert not result.errors
    assert result.data
    trigger_id = result.data["CoreNodeTriggerRuleCreate"]["object"]["id"]

    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_NODE_TRIGGER_RELATIONSHIP_MATCH,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"relationship_name": "missing_relationship", "trigger": trigger_id, "peer": str(uuid4())},
    )

    assert "The relationship missing_relationship doesn't exist on related node trigger using TestCar" in str(
        result.errors
    )

    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_NODE_TRIGGER_RELATIONSHIP_MATCH,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"relationship_name": "owner", "trigger": trigger_id, "peer": str(uuid4())},
    )
    assert not result.errors
    assert result.data
    relationship_match_id = result.data["CoreNodeTriggerRelationshipMatchCreate"]["object"]["id"]

    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_NODE_TRIGGER_RELATIONSHIP_MATCH,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"relationship_name": "leasing_company", "id": relationship_match_id},
    )

    assert "The relationship leasing_company doesn't exist on related node trigger using TestCar" in str(result.errors)

    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_NODE_TRIGGER_RELATIONSHIP_MATCH,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"relationship_name": "owner", "id": relationship_match_id, "peer": str(uuid4())},
    )
    assert not result.errors
    assert result.data


CREATE_NODE_TRIGGER = """
mutation(
    $name: String!,
    $node_kind: String!,
    $action: String!,
    )
{
    CoreNodeTriggerRuleCreate(data: {
        name: { value: $name},
        node_kind: {value: $node_kind}
        action: {id: $action}
        mutation_action: { value: "updated" }
    })
    {
        ok
        object {
            id
        }
    }
}
"""


CREATE_NODE_TRIGGER_ATTRIBUTE_MATCH = """
mutation(
    $attribute_name: String!,
    $value: String,
    $trigger: String!,
    )
{
    CoreNodeTriggerAttributeMatchCreate(data: {
        attribute_name: { value: $attribute_name},
        value: { value: $value}
        trigger: {id: $trigger}
    })
    {
        ok
        object {
            id
        }
    }
}
"""

CREATE_NODE_TRIGGER_RELATIONSHIP_MATCH = """
mutation(
    $relationship_name: String!,
    $peer: String,
    $trigger: String!,
    )
{
    CoreNodeTriggerRelationshipMatchCreate(data: {
        relationship_name: { value: $relationship_name},
        peer: { value: $peer}
        trigger: {id: $trigger}
    })
    {
        ok
        object {
            id
        }
    }
}
"""


UPDATE_NODE_TRIGGER_ATTRIBUTE_MATCH = """
mutation(
    $id: String!,
    $attribute_name: String!
)
{
    CoreNodeTriggerAttributeMatchUpdate(data: {
        id: $id,
        attribute_name: { value: $attribute_name}
    })
    {
        ok
        object {
            id
        }
    }
}
"""

UPDATE_NODE_TRIGGER_RELATIONSHIP_MATCH = """
mutation(
    $id: String!,
    $relationship_name: String!,
    $peer: String
)
{
    CoreNodeTriggerRelationshipMatchUpdate(data: {
        id: $id,
        relationship_name: { value: $relationship_name}
        peer: { value: $peer }
    })
    {
        ok
        object {
            id
        }
    }
}
"""
