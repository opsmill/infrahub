from typing import Any

import pytest
from graphql import ExecutionResult
from infrahub_sdk.graphql import Query
from prefect.artifacts import ArtifactRequest
from prefect.client.orchestration import PrefectClient, get_client
from prefect.flows import FlowRun
from prefect.states import State

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.tasks.dummy import dummy_flow, dummy_flow_broken
from infrahub.workflows.constants import TAG_NAMESPACE, WorkflowTag
from tests.helpers.graphql import graphql

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
        workflow
        parameters
        related_node
        related_node_kind
        related_nodes {
            id
            kind
        }
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
        related_nodes {
            id
            kind
        }
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


QUERY_TASK_WITH_LOG_OFFSET = """
query TaskQuery(
    $related_nodes: [String]
) {
  InfrahubTask(related_node__ids: $related_nodes, log_offset: 1, log_limit: 10) {
    count
    edges {
      node {
        conclusion
        created_at
        id
        related_node
        related_node_kind
        related_nodes {
            id
            kind
        }
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
async def prefect_client(prefect_test_fixture):
    async with get_client(sync_client=False) as client:
        yield client


@pytest.fixture
async def delete_flow_runs(prefect_client: PrefectClient):
    flows = await prefect_client.read_flow_runs()
    for flow in flows:
        await prefect_client.delete_flow_run(flow_run_id=flow.id)


@pytest.fixture
async def flow_runs_data(prefect_client: PrefectClient, tag_blue, tag_red, account_bob) -> dict[str, FlowRun]:
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
            flow=dummy_flow_broken,
            name="dummy-completed-no-tag",
            parameters={"firstname": "jane", "lastname": "doe"},
            tags=[],
            state=State(type="COMPLETED"),
        ),
        await prefect_client.create_flow_run(
            flow=dummy_flow,
            name="dummy-completed-no-branch",
            parameters={"firstname": "jane", "lastname": "doe"},
            tags=[TAG_NAMESPACE],
            state=State(type="COMPLETED"),
        ),
        await prefect_client.create_flow_run(
            flow=dummy_flow_broken,
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
            flow=dummy_flow_broken,
            name="dummy-completed-account-br1-db",
            parameters={"firstname": "xxxx", "lastname": "zzzzz"},
            tags=[
                TAG_NAMESPACE,
                WorkflowTag.RELATED_NODE.render(identifier=account_bob.get_id()),
                WorkflowTag.RELATED_NODE.render(identifier=tag_red.get_id()),
                branch1_tag,
                db_tag,
            ],
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
            flow=dummy_flow_broken,
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


async def run_query(db: InfrahubDatabase, branch: Branch, query: str, variables: dict[str, Any]) -> ExecutionResult:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    return await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )


async def test_task_query_prefect(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    delete_flow_runs,
    flow_runs_data: dict[str, FlowRun],
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
        "dummy-completed-no-branch",
        "dummy-running-br1",
        "dummy-running-br1-db",
        "dummy-scheduled-blue-db",
        "dummy-scheduled-br1-db",
    ]
    assert result.data["InfrahubTask"]["count"] == len(task_names)


async def test_task_query_filter_workflow(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    delete_flow_runs,
    flow_runs_data: dict[str, FlowRun],
):
    QUERY = """
    query {
        InfrahubTask(workflow: ["dummy-flow"]) {
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
        variables={},
    )
    assert result.errors is None
    assert result.data

    task_names = sorted([task["node"]["title"] for task in result.data["InfrahubTask"]["edges"]])
    assert task_names == [
        "dummy-completed-br1-db",
        "dummy-completed-no-branch",
        "dummy-running-br1",
        "dummy-scheduled-blue-db",
        "dummy-scheduled-br1-db",
    ]
    assert result.data["InfrahubTask"]["count"] == len(task_names)


async def test_task_query_filter_workflow_state(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, delete_flow_runs, flow_runs_data
):
    QUERY = """
    query {
        InfrahubTask(workflow: ["dummy-flow"], state: [RUNNING, SCHEDULED]) {
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
        variables={},
    )
    assert result.errors is None
    assert result.data

    task_names = sorted([task["node"]["title"] for task in result.data["InfrahubTask"]["edges"]])
    assert task_names == ["dummy-running-br1", "dummy-scheduled-blue-db", "dummy-scheduled-br1-db"]
    assert result.data["InfrahubTask"]["count"] == len(task_names)


async def test_task_query_filter_id(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, delete_flow_runs, flow_runs_data
):
    dummy_completed_br1_db = flow_runs_data["dummy-completed-br1-db"]
    dummy_running_br1 = flow_runs_data["dummy-running-br1"]

    query = Query(
        query={
            "InfrahubTask": {
                "@filters": {"ids": [str(dummy_completed_br1_db.id), str(dummy_running_br1.id)]},
                "count": None,
                "edges": {"node": {"id": None, "title": None}},
            }
        }
    )

    result = await run_query(
        db=db,
        branch=default_branch,
        query=query.render(),
        variables={},
    )
    assert result.errors is None
    assert result.data

    task_names = sorted([task["node"]["title"] for task in result.data["InfrahubTask"]["edges"]])
    assert task_names == [
        "dummy-completed-br1-db",
        "dummy-running-br1",
    ]
    assert result.data["InfrahubTask"]["count"] == len(task_names)


async def test_task_query_filter_branch(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, delete_flow_runs, flow_runs_data
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


async def test_task_query_filter_state(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, delete_flow_runs, flow_runs_data
):
    QUERY = """
    query {
        InfrahubTask(state: [RUNNING, COMPLETED]) {
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
        variables={},
    )
    assert result.errors is None
    assert result.data

    task_names = sorted([task["node"]["title"] for task in result.data["InfrahubTask"]["edges"]])
    assert task_names == [
        "dummy-completed-account-br1-db",
        "dummy-completed-br1-db",
        "dummy-completed-no-branch",
        "dummy-running-br1",
        "dummy-running-br1-db",
    ]
    assert result.data["InfrahubTask"]["count"] == len(task_names)


async def test_task_query_partial_text(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, delete_flow_runs, flow_runs_data
):
    QUERY = """
    query {
        InfrahubTask(q: "br1") {
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
        "dummy-scheduled-br1-db",
    ]
    assert result.data["InfrahubTask"]["count"] == len(task_names)


async def test_task_query_filter_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    tag_blue,
    tag_red,
    account_bob,
    account_bill,
    delete_flow_runs,
    flow_runs_data: dict[str, FlowRun],
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
            "related_nodes": [
                {
                    "id": tag_blue.get_id(),
                    "kind": "BuiltinTag",
                },
            ],
            "title": flow.name,
            "updated_at": flow.updated.to_iso8601_string(),
            "start_time": None,
            "workflow": "dummy-flow",
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
                f"infrahub.app/node/{tag_red.get_id()}",
                "infrahub.app/branch/branch1",
                "infrahub.app/database-change",
            ],
            "parameters": {"firstname": "xxxx", "lastname": "zzzzz"},
            "related_node": account_bob.get_id(),
            "related_node_kind": "CoreAccount",
            "related_nodes": [
                {
                    "id": account_bob.get_id(),
                    "kind": "CoreAccount",
                },
                {
                    "id": tag_red.get_id(),
                    "kind": "BuiltinTag",
                },
            ],
            "title": flow.name,
            "updated_at": flow.updated.to_iso8601_string(),
            "start_time": None,
            "workflow": "dummy-flow-broken",
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
    delete_flow_runs,
    flow_runs_data: dict[str, FlowRun],
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
        "dummy-completed-no-branch",
        "dummy-running-br1",
        "dummy-running-br1-db",
        "dummy-scheduled-blue-db",
        "dummy-scheduled-br1-db",
    ]
    assert result.data["InfrahubTask"]["count"] == len(task_names)


async def test_task_query_with_log_offset(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    tag_blue,
    account_bob,
    delete_flow_runs,
    flow_runs_data: dict[str, FlowRun],
):
    """
    In unit tests logs are not forwarded to the Prefect server for unknown reasons.
    Therefore this test mainly tests log_offset and log_limit do not break the query when they are specified,
    but their logic itself is not tested on a large amount of logs.
    """

    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK_WITH_LOG_OFFSET,
        variables={},
    )
    assert result.errors is None
    assert result.data

    task_names = sorted([task["node"]["title"] for task in result.data["InfrahubTask"]["edges"]])
    assert task_names == [
        "dummy-completed-account-br1-db",
        "dummy-completed-br1-db",
        "dummy-completed-no-branch",
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
    delete_flow_runs,
    flow_runs_data: dict[str, FlowRun],
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
            "related_nodes": [
                {
                    "id": tag_red.get_id(),
                    "kind": "BuiltinTag",
                },
            ],
            "title": flow.name,
            "updated_at": flow.updated.to_iso8601_string(),
            "start_time": flow.start_time.to_iso8601_string(),
            "workflow": "dummy-flow",
        }
    }


async def test_task_no_count(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    tag_blue,
    account_bob,
    delete_flow_runs,
    flow_runs_data: dict[str, FlowRun],
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
        "dummy-completed-no-branch",
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
    delete_flow_runs,
    flow_runs_data: dict[str, FlowRun],
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
    assert result.data["InfrahubTask"]["count"] == 7
