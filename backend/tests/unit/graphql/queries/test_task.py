from typing import Any, Dict
from uuid import uuid4

import pytest
from graphql import ExecutionResult, graphql
from prefect.artifacts import ArtifactRequest
from prefect.client.orchestration import PrefectClient, get_client
from prefect.states import State
from prefect.testing.utilities import prefect_test_harness

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.tasks.dummy import dummy_flow
from infrahub.workflows.constants import TAG_NAMESPACE, WorkflowTag

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
        state
        progress
        branch
        tags
        parameters
        related_node
        related_node_kind
        title
        updated_at
        start_time
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


@pytest.fixture
def local_prefect_server():
    with prefect_test_harness():
        yield


@pytest.fixture
async def tag_blue(db: InfrahubDatabase, default_branch: Branch) -> Node:
    blue = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await blue.new(db=db, name="Blue", description="The Blue tag")
    await blue.save(db=db)
    return blue


@pytest.fixture
async def tag_red(db: InfrahubDatabase, default_branch: Branch) -> Node:
    blue = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await blue.new(db=db, name="Red", description="The REd tag")
    await blue.save(db=db)
    return blue


@pytest.fixture
async def account_bob(db: InfrahubDatabase, default_branch: Branch) -> Node:
    bob = await Node.init(db=db, schema=InfrahubKind.ACCOUNT, branch=default_branch)
    await bob.new(db=db, name="bob", password=str(uuid4()))
    await bob.save(db=db)
    return bob


@pytest.fixture
async def account_bill(db: InfrahubDatabase, default_branch: Branch) -> Node:
    bill = await Node.init(db=db, schema=InfrahubKind.ACCOUNT, branch=default_branch)
    await bill.new(db=db, name="bill", password=str(uuid4()))
    await bill.save(db=db)
    return bill


@pytest.fixture
async def prefect_client(local_prefect_server):
    async with get_client(sync_client=False) as client:
        yield client


@pytest.fixture
async def flow_runs_data(prefect_client: PrefectClient, tag_blue, account_bob):
    branch1_tag = WorkflowTag.BRANCH.render(identifier="branch1")
    db_tag = WorkflowTag.DATABASE_CHANGE.render()
    items = [
        await prefect_client.create_flow_run(
            flow=dummy_flow,
            name="dummy-completed-br1-db",
            parameters={"firstname": "john", "lastname": "doe"},
            tags=[TAG_NAMESPACE, branch1_tag, db_tag],
            state=State(type="COMPLETED"),
        ),
        await prefect_client.create_flow_run(
            flow=dummy_flow,
            name="dummy-completed-no-tag",
            parameters={"firstname": "jane", "lastname": "doe"},
            tags=[],
            state=State(type="COMPLETED"),
        ),
        await prefect_client.create_flow_run(
            flow=dummy_flow,
            name="dummy-scheduled-no-tag",
            parameters={"firstname": "jane", "lastname": "doe"},
            tags=[],
            state=State(type="SCHEDULED"),
        ),
        await prefect_client.create_flow_run(
            flow=dummy_flow,
            name="dummy-scheduled-blue-db",
            parameters={"firstname": "xxxx", "lastname": "yyy"},
            tags=[TAG_NAMESPACE, WorkflowTag.RELATED_NODE.render(identifier=tag_blue.get_id()), db_tag],
            state=State(type="SCHEDULED"),
        ),
        await prefect_client.create_flow_run(
            flow=dummy_flow,
            name="dummy-completed-account-br1-db",
            parameters={"firstname": "xxxx", "lastname": "zzzzz"},
            tags=[TAG_NAMESPACE, WorkflowTag.RELATED_NODE.render(identifier=account_bob.get_id()), branch1_tag, db_tag],
            state=State(type="COMPLETED"),
        ),
        await prefect_client.create_flow_run(
            flow=dummy_flow,
            name="dummy-scheduled-br1-db",
            parameters={"firstname": "xxxx", "lastname": "yyy"},
            tags=[TAG_NAMESPACE, branch1_tag, db_tag],
            state=State(type="SCHEDULED"),
        ),
        await prefect_client.create_flow_run(
            flow=dummy_flow,
            name="dummy-running-br1-db",
            parameters={"firstname": "xxxx", "lastname": "yyy"},
            tags=[TAG_NAMESPACE, branch1_tag, db_tag],
            state=State(type="RUNNING"),
        ),
        await prefect_client.create_flow_run(
            flow=dummy_flow,
            name="dummy-running-br1",
            parameters={"firstname": "xxxx", "lastname": "yyy"},
            tags=[TAG_NAMESPACE, branch1_tag],
            state=State(type="RUNNING"),
        ),
    ]

    return {item.name: item for item in items}


async def run_query(db: InfrahubDatabase, branch: Branch, query: str, variables: Dict[str, Any]) -> ExecutionResult:
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch)
    return await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )


async def test_task_query_infrahub(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, local_prefect_server
):
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
    assert result.errors is None
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
    assert result.errors is None
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
    assert result.errors is None
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
    assert result.errors is None
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
    assert result.errors is None
    assert result.data

    all_tasks = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK,
        variables={},
    )
    assert all_tasks.errors is None
    assert all_tasks.data
    assert all_tasks.data["InfrahubTask"]["count"] == 5

    blue_tasks = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK,
        variables={"related_nodes": blue.get_id()},
    )
    assert blue_tasks.errors is None
    assert blue_tasks.data
    assert blue_tasks.data["InfrahubTask"]["count"] == 3

    red_blue_tasks = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK,
        variables={"related_nodes": [red.get_id(), blue.get_id()]},
    )
    assert red_blue_tasks.errors is None
    assert red_blue_tasks.data
    assert red_blue_tasks.data["InfrahubTask"]["count"] == 4

    all_logs = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK_WITH_LOGS,
        variables={},
    )
    assert all_logs.errors is None
    assert all_logs.data
    logs = []
    for task in all_logs.data["InfrahubTask"]["edges"]:
        [logs.append(log) for log in task["node"]["logs"]["edges"]]

    assert len(logs) == 6


async def test_task_query_prefect(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, flow_runs_data
):
    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK_WITH_LOGS,
        variables={},
    )
    assert result.errors is None
    assert result.data

    task_names = sorted([task["node"]["title"] for task in result.data["InfrahubTask"]["edges"]])
    assert task_names == [
        "dummy-completed-account-br1-db",
        "dummy-completed-br1-db",
        "dummy-running-br1",
        "dummy-running-br1-db",
        "dummy-scheduled-blue-db",
        "dummy-scheduled-br1-db",
    ]
    assert result.data["InfrahubTask"]["count"] == len(task_names)


async def test_task_query_filter_branch(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, flow_runs_data
):
    QUERY = """
    query TaskQuery(
        $branch_name: String!
    ) {
        InfrahubTask(branch: $branch_name) {
            count
            edges {
                node {
                    id
                    title
                }
            }
        }
    }
    """
    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY,
        variables={"branch_name": "branch1"},
    )
    assert result.errors is None
    assert result.data

    task_names = sorted([task["node"]["title"] for task in result.data["InfrahubTask"]["edges"]])
    assert task_names == [
        "dummy-completed-account-br1-db",
        "dummy-completed-br1-db",
        "dummy-running-br1",
        "dummy-running-br1-db",
        "dummy-scheduled-br1-db",
    ]
    assert result.data["InfrahubTask"]["count"] == len(task_names)


async def test_task_query_filter_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    tag_blue,
    account_bob,
    account_bill,
    flow_runs_data,
):
    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK,
        variables={"related_nodes": [tag_blue.get_id()]},
    )
    assert result.errors is None
    assert result.data

    flow = flow_runs_data["dummy-scheduled-blue-db"]
    assert result.data["InfrahubTask"]["edges"][0] == {
        "node": {
            "conclusion": "unknown",
            "created_at": flow.created.to_iso8601_string(),
            "id": str(flow.id),
            "state": "SCHEDULED",
            "progress": None,
            "branch": None,
            "tags": ["infrahub.app", f"infrahub.app/node/{tag_blue.get_id()}", "infrahub.app/database-change"],
            "parameters": {"firstname": "xxxx", "lastname": "yyy"},
            "related_node": tag_blue.get_id(),
            "related_node_kind": "BuiltinTag",
            "title": flow.name,
            "updated_at": flow.updated.to_iso8601_string(),
            "start_time": None,
        }
    }

    # ----------------------------------------------
    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK,
        variables={"related_nodes": [account_bob.get_id()]},
    )
    assert result.errors is None
    assert result.data

    flow = flow_runs_data["dummy-completed-account-br1-db"]
    assert result.data["InfrahubTask"]["edges"][0] == {
        "node": {
            "conclusion": "success",
            "created_at": flow.created.to_iso8601_string(),
            "id": str(flow.id),
            "state": "COMPLETED",
            "progress": None,
            "branch": "branch1",
            "tags": [
                "infrahub.app",
                f"infrahub.app/node/{account_bob.get_id()}",
                "infrahub.app/branch/branch1",
                "infrahub.app/database-change",
            ],
            "parameters": {"firstname": "xxxx", "lastname": "zzzzz"},
            "related_node": account_bob.get_id(),
            "related_node_kind": "CoreAccount",
            "title": flow.name,
            "updated_at": flow.updated.to_iso8601_string(),
            "start_time": None,
        }
    }

    # ----------------------------------------------
    # Query with a related node not associated with any tasks
    # ----------------------------------------------
    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK,
        variables={"related_nodes": [account_bill.get_id()]},
    )
    assert result.errors is None
    assert result.data

    task_names = sorted([task["node"]["title"] for task in result.data["InfrahubTask"]["edges"]])
    assert task_names == []
    assert result.data["InfrahubTask"]["count"] == len(task_names)


async def test_task_query_both(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    tag_blue,
    account_bob,
    flow_runs_data,
):
    create_task = await run_query(
        db=db,
        branch=default_branch,
        query=CREATE_TASK,
        variables={
            "conclusion": "UNKNOWN",
            "title": "Blue Task 1",
            "related_node": tag_blue.get_id(),
            "created_by": account_bob.get_id(),
            "logs": {"message": "Starting task", "severity": "INFO"},
        },
    )
    assert create_task.errors is None
    assert create_task.data

    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK_WITH_LOGS,
        variables={},
    )
    assert result.errors is None
    assert result.data

    task_names = sorted([task["node"]["title"] for task in result.data["InfrahubTask"]["edges"]])
    assert task_names == [
        "Blue Task 1",
        "dummy-completed-account-br1-db",
        "dummy-completed-br1-db",
        "dummy-running-br1",
        "dummy-running-br1-db",
        "dummy-scheduled-blue-db",
        "dummy-scheduled-br1-db",
    ]
    assert result.data["InfrahubTask"]["count"] == len(task_names)


async def test_task_branch_status(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    tag_blue,
    account_bob,
    flow_runs_data,
):
    QUERY = """
    query TaskQuery(
        $branch_name: String!
    ) {
        InfrahubTaskBranchStatus(branch: $branch_name) {
            count
            edges {
                node {
                    id
                    title
                }
            }
        }
    }
    """
    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY,
        variables={"branch_name": "branch1"},
    )
    assert result.errors is None
    assert result.data

    task_names = sorted([task["node"]["title"] for task in result.data["InfrahubTaskBranchStatus"]["edges"]])
    assert task_names == ["dummy-running-br1-db", "dummy-scheduled-br1-db"]
    assert result.data["InfrahubTaskBranchStatus"]["count"] == len(task_names)


async def test_task_query_progress(
    db: InfrahubDatabase,
    default_branch: Branch,
    prefect_client: PrefectClient,
    register_core_models_schema: None,
    tag_red,
):
    flow = await prefect_client.create_flow_run(
        flow=dummy_flow,
        name="dummy-running-red_tag",
        parameters={"firstname": "xxxx", "lastname": "yyy"},
        tags=[TAG_NAMESPACE, WorkflowTag.RELATED_NODE.render(identifier=tag_red.get_id())],
        state=State(type="RUNNING"),
    )

    await prefect_client.create_artifact(
        artifact=ArtifactRequest(
            type="progress",
            key="infrahub-task-progression",
            description="progress bar",
            flow_run_id=flow.id,
            data=33.33,
        )
    )

    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK,
        variables={"related_nodes": [tag_red.get_id()]},
    )

    assert result.errors is None
    assert result.data

    assert result.data["InfrahubTask"]["edges"][0] == {
        "node": {
            "conclusion": "unknown",
            "created_at": flow.created.to_iso8601_string(),
            "id": str(flow.id),
            "state": "RUNNING",
            "progress": 33.33,
            "branch": None,
            "tags": ["infrahub.app", f"infrahub.app/node/{tag_red.get_id()}"],
            "parameters": {"firstname": "xxxx", "lastname": "yyy"},
            "related_node": tag_red.get_id(),
            "related_node_kind": "BuiltinTag",
            "title": flow.name,
            "updated_at": flow.updated.to_iso8601_string(),
            "start_time": flow.start_time.to_iso8601_string(),
        }
    }


async def test_task_no_count(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    tag_blue,
    account_bob,
    flow_runs_data,
):
    QUERY = """
    query TaskQuery {
        InfrahubTask {
            edges {
                node {
                    conclusion
                    title
                    state
                }
            }
        }
    }
    """

    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY,
        variables={},
    )

    assert result.errors is None
    task_names = sorted([task["node"]["title"] for task in result.data["InfrahubTask"]["edges"]])
    assert task_names == [
        "dummy-completed-account-br1-db",
        "dummy-completed-br1-db",
        "dummy-running-br1",
        "dummy-running-br1-db",
        "dummy-scheduled-blue-db",
        "dummy-scheduled-br1-db",
    ]


async def test_task_only_count(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    tag_blue,
    account_bob,
    flow_runs_data,
):
    QUERY = """
    query TaskQuery {
        InfrahubTask {
            count
        }
    }
    """

    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY,
        variables={},
    )

    assert result.errors is None
    assert result.data["InfrahubTask"]["count"] == 6
