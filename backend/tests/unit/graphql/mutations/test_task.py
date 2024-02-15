from graphql import graphql

from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params

CREATE_TASK = """
mutation CreateTask(
    $conclusion: TaskConclusion!,
    $title: String!,
    $task_id: UUID,
    $created_by: String,
    $related_node: String!,
    $logs: [RelatedTaskLogCreateInput]
    ) {
    InfrahubTaskCreate(
        data: {
            id: $task_id,
            created_by: $created_by,
            title: $title,
            conclusion: $conclusion,
            related_node: $related_node,
            logs: $logs
        }
    ) {
        ok
        object {
            id
        }
    }
}
"""

UPDATE_TASK = """
mutation UpdateTask(
    $conclusion: TaskConclusion,
    $title: String,
    $task_id: UUID!,
    $logs: [RelatedTaskLogCreateInput]
    ) {
    InfrahubTaskUpdate(
        data: {
            id: $task_id,
            title: $title,
            conclusion: $conclusion,
            logs: $logs
        }
    ) {
        ok
    }
}
"""


async def test_task_create(db: InfrahubDatabase, default_branch, car_person_schema: None):
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="John", height=180)
    await person.save(db=db)

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_TASK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"conclusion": "SUCCESS", "title": "Test Task", "related_node": person.get_id()},
    )

    assert not result.errors


async def test_task_create_and_update(db: InfrahubDatabase, default_branch, car_person_schema: None):
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="John", height=180)
    await person.save(db=db)

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_TASK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "conclusion": "UNKNOWN",
            "title": "Test Task",
            "related_node": person.get_id(),
            "logs": {"message": "Starting task", "severity": "INFO"},
        },
    )

    assert not result.errors
    assert result.data
    task_id = result.data["InfrahubTaskCreate"]["object"]["id"]

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_TASK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "conclusion": "SUCCESS",
            "logs": [
                {"message": "Processing Task", "severity": "INFO"},
                {"message": "Finishing Task", "severity": "INFO"},
            ],
            "task_id": task_id,
        },
    )

    assert not result.errors
