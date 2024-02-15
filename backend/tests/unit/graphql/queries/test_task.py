from typing import Any, Dict
from uuid import uuid4

from graphql import ExecutionResult, graphql

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
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

QUERY_TASK = """
query TaskQuery(
    $related_nodes: [String]
) {
  InfrahubTask(related_node__ids: $related_nodes) {
    count
    edges {
      node {
        conclusion
        created_at
        id
        related_node
        related_node_kind
        title
        updated_at
      }
    }
  }
}
"""

QUERY_TASK_WITH_LOGS = """
query TaskQuery(
    $related_nodes: [String]
) {
  InfrahubTask(related_node__ids: $related_nodes) {
    count
    edges {
      node {
        conclusion
        created_at
        id
        related_node
        related_node_kind
        title
        updated_at
        logs {
            edges {
                node {
                    id
                    message
                    severity
                    timestamp
                }
            }
        }
      }
    }
  }
}
"""


async def test_task_query(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None):
    red = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await red.new(db=db, name="Red", description="The Red tag")
    await red.save(db=db)

    green = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await green.new(db=db, name="Green", description="The Green tag")
    await green.save(db=db)

    blue = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await blue.new(db=db, name="Blue", description="The Blue tag")
    await blue.save(db=db)

    bob = await Node.init(db=db, schema=InfrahubKind.ACCOUNT, branch=default_branch)
    await bob.new(db=db, name="bob", password=str(uuid4()))
    await bob.save(db=db)

    result = await run_query(
        db=db,
        branch=default_branch,
        query=CREATE_TASK,
        variables={
            "conclusion": "UNKNOWN",
            "title": "Blue Task 1",
            "related_node": blue.get_id(),
            "created_by": bob.get_id(),
            "logs": {"message": "Starting task", "severity": "INFO"},
        },
    )
    assert result.data

    result = await run_query(
        db=db,
        branch=default_branch,
        query=CREATE_TASK,
        variables={
            "conclusion": "UNKNOWN",
            "title": "Red Task 1",
            "related_node": red.get_id(),
            "created_by": bob.get_id(),
            "logs": {"message": "Starting task", "severity": "INFO"},
        },
    )
    assert result.data

    result = await run_query(
        db=db,
        branch=default_branch,
        query=CREATE_TASK,
        variables={
            "conclusion": "UNKNOWN",
            "title": "Green Task 1",
            "related_node": green.get_id(),
            "created_by": bob.get_id(),
            "logs": {"message": "Starting task", "severity": "INFO"},
        },
    )
    assert result.data

    result = await run_query(
        db=db,
        branch=default_branch,
        query=CREATE_TASK,
        variables={
            "conclusion": "UNKNOWN",
            "title": "Blue Task 1",
            "related_node": blue.get_id(),
            "created_by": bob.get_id(),
            "logs": {"message": "Starting task", "severity": "INFO"},
        },
    )
    assert result.data

    result = await run_query(
        db=db,
        branch=default_branch,
        query=CREATE_TASK,
        variables={
            "conclusion": "SUCCESS",
            "title": "Blue Task 2",
            "related_node": blue.get_id(),
            "created_by": bob.get_id(),
            "logs": [
                {"message": "Starting task", "severity": "INFO"},
                {"message": "Finalizing task", "severity": "INFO"},
            ],
        },
    )
    assert result.data

    all_tasks = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK,
        variables={},
    )
    assert all_tasks.data
    assert all_tasks.data["InfrahubTask"]["count"] == 5

    blue_tasks = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK,
        variables={"related_nodes": blue.get_id()},
    )
    assert blue_tasks.data
    assert blue_tasks.data["InfrahubTask"]["count"] == 3

    red_blue_tasks = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK,
        variables={"related_nodes": [red.get_id(), blue.get_id()]},
    )
    assert red_blue_tasks.data
    assert red_blue_tasks.data["InfrahubTask"]["count"] == 4

    all_logs = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK_WITH_LOGS,
        variables={},
    )
    assert all_logs.data
    logs = []
    for task in all_logs.data["InfrahubTask"]["edges"]:
        [logs.append(log) for log in task["node"]["logs"]["edges"]]

    assert len(logs) == 6


async def run_query(db: InfrahubDatabase, branch: Branch, query: str, variables: Dict[str, Any]) -> ExecutionResult:
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    return await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )
