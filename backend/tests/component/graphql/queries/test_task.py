from collections.abc import AsyncGenerator, Generator
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
from infrahub.webhook.tasks.process import webhook_send
from infrahub.workers.dependencies import clear_singletons
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


QUERY_TASK_TYPED = """
query TaskQuery {
  InfrahubTask {
    count
    edges {
      node {
        __typename
        id
        title
        workflow
        available_actions {
            action
            available
            unavailability_reason
        }
        error {
            status_class
            message
            remediation
        }
        ... on WebhookDeliveryTask {
            http_request {
                url
                headers
            }
            http_response {
                status_code
                body
                latency_ms
            }
        }
      }
    }
  }
}
"""


@pytest.fixture(autouse=True)
def cache_singleton_with_redis_settings(redis: dict[int, int] | None) -> Generator[None, None, None]:
    """The task queries read flow-run counts through the process-wide cache singleton.

    Depending on which modules ran earlier in this process, that singleton may have been
    built while the redis settings of this module were not applied yet, pointing it at a
    cache that does not exist. Drop it so it is rebuilt against the active settings, and
    drop it again afterwards so later modules do not inherit it.
    """
    clear_singletons()
    yield
    clear_singletons()


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
async def prefect_client(prefect_test_fixture: Generator[None, None, None]) -> AsyncGenerator[PrefectClient, None]:
    async with get_client(sync_client=False) as client:
        yield client


@pytest.fixture
async def delete_flow_runs(prefect_client: PrefectClient) -> None:
    flows = await prefect_client.read_flow_runs()
    for flow in flows:
        await prefect_client.delete_flow_run(flow_run_id=flow.id)


@pytest.fixture
async def flow_runs_data(
    prefect_client: PrefectClient, tag_blue: Node, tag_red: Node, account_bob: Node
) -> dict[str, FlowRun]:
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
    delete_flow_runs: None,
    flow_runs_data: dict[str, FlowRun],
) -> None:
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
    delete_flow_runs: None,
    flow_runs_data: dict[str, FlowRun],
) -> None:
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
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    delete_flow_runs: None,
    flow_runs_data: dict[str, FlowRun],
) -> None:
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
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    delete_flow_runs: None,
    flow_runs_data: dict[str, FlowRun],
) -> None:
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
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    delete_flow_runs: None,
    flow_runs_data: dict[str, FlowRun],
) -> None:
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
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    delete_flow_runs: None,
    flow_runs_data: dict[str, FlowRun],
) -> None:
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
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    delete_flow_runs: None,
    flow_runs_data: dict[str, FlowRun],
) -> None:
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
    tag_blue: Node,
    tag_red: Node,
    account_bob: Node,
    account_bill: Node,
    delete_flow_runs: None,
    flow_runs_data: dict[str, FlowRun],
) -> None:
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
            "created_at": flow.created.isoformat(),
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
            "updated_at": flow.updated.isoformat(),
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
            "created_at": flow.created.isoformat(),
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
            "updated_at": flow.updated.isoformat(),
            "start_time": flow.start_time.isoformat(),
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
    tag_blue: Node,
    account_bob: Node,
    delete_flow_runs: None,
    flow_runs_data: dict[str, FlowRun],
) -> None:
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
    tag_blue: Node,
    account_bob: Node,
    delete_flow_runs: None,
    flow_runs_data: dict[str, FlowRun],
) -> None:
    """In unit tests logs are not forwarded to the Prefect server for unknown reasons.

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
    tag_blue: Node,
    account_bob: Node,
    delete_flow_runs: None,
    flow_runs_data: dict[str, FlowRun],
) -> None:
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
    tag_red: Node,
) -> None:
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
            "created_at": flow.created.isoformat(),
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
            "updated_at": flow.updated.isoformat(),
            "start_time": flow.start_time.isoformat(),
            "workflow": "dummy-flow",
        }
    }


async def test_task_no_count(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    tag_blue: Node,
    account_bob: Node,
    delete_flow_runs: None,
    flow_runs_data: dict[str, FlowRun],
) -> None:
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


async def test_task_query_polymorphic_typing(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    prefect_client: PrefectClient,
    delete_flow_runs: None,
    flow_runs_data: dict[str, FlowRun],
) -> None:
    """A webhook-send run resolves to the delivery type; every other run stays a plain task node."""
    delivery = await prefect_client.create_flow_run(
        flow=webhook_send,
        name="webhook-send-completed",
        parameters={
            "webhook_id": "17b3b2f0-89aa-4fdd-8beb-c1e5b0e5d661",
            "webhook_kind": "CoreStandardWebhook",
            "webhook_name": "component-test-webhook",
            "payload": {"event_type": "branch.created"},
        },
        tags=[TAG_NAMESPACE],
        state=State(type="COMPLETED"),
    )

    result = await run_query(
        db=db,
        branch=default_branch,
        query=QUERY_TASK_TYPED,
        variables={},
    )
    assert result.errors is None
    assert result.data

    nodes = {edge["node"]["title"]: edge["node"] for edge in result.data["InfrahubTask"]["edges"]}

    delivery_node = nodes["webhook-send-completed"]
    assert delivery_node["__typename"] == "WebhookDeliveryTask"
    assert delivery_node["id"] == str(delivery.id)
    assert delivery_node["workflow"] == "webhook-send"
    assert delivery_node["available_actions"] == [
        {"action": "RETRY", "available": True, "unavailability_reason": None},
        {"action": "CANCEL", "available": False, "unavailability_reason": "Delivery already settled"},
    ]
    # The captured request/response artifact is not written yet: the delivery-specific fields resolve to null.
    assert delivery_node["http_request"] is None
    assert delivery_node["http_response"] is None
    assert delivery_node["error"] is None

    dummy_node = nodes["dummy-completed-br1-db"]
    assert dummy_node["__typename"] == "TaskNode"
    assert dummy_node["workflow"] == "dummy-flow"
    assert dummy_node["available_actions"] == []
    # The classified error is a common field carried by every task, null when the task has none.
    assert dummy_node["error"] is None
    assert "http_request" not in dummy_node


async def test_task_query_fragment_selecting_only_common_fields(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    prefect_client: PrefectClient,
    delete_flow_runs: None,
) -> None:
    """An inline fragment matches a delivery even when it selects no delivery-specific field.

    The concrete type is resolved from the run's workflow name, which nothing in this selection
    names explicitly — the fragment's fields are all common ones — so this guards the invariant
    that the discriminant is fetched with the runs rather than derived from the selected fields.
    """
    delivery = await prefect_client.create_flow_run(
        flow=webhook_send,
        name="webhook-send-fragment",
        parameters={
            "webhook_id": "17b3b2f0-89aa-4fdd-8beb-c1e5b0e5d661",
            "webhook_kind": "CoreStandardWebhook",
            "webhook_name": "fragment-test-webhook",
            "payload": {"event_type": "branch.created"},
        },
        tags=[TAG_NAMESPACE],
        state=State(type="COMPLETED"),
    )

    QUERY = """
    query {
      InfrahubTask {
        edges {
          node {
            id
            ... on WebhookDeliveryTask {
                title
                state
            }
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

    node = result.data["InfrahubTask"]["edges"][0]["node"]
    assert node == {
        "id": str(delivery.id),
        "title": "webhook-send-fragment",
        "state": "COMPLETED",
    }


async def test_task_only_count(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    tag_blue: Node,
    account_bob: Node,
    delete_flow_runs: None,
    flow_runs_data: dict[str, FlowRun],
) -> None:
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
