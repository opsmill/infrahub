from uuid import uuid4

from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId
from prefect.client.schemas.objects import State, StateType

from infrahub.branch.tasks import purge_deleted_branch_tasks
from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter
from infrahub.workflows.constants import TAG_NAMESPACE, WorkflowTag


@flow
def _noop_flow() -> None:
    """A trivial flow used only to create branch-tagged flow runs standing in for tasks."""


async def test_purge_removes_settled_tasks_of_a_deleted_branch_but_leaves_running_ones(
    prefect_client: PrefectClient,
) -> None:
    """A deleted branch's settled tasks are removed so completed tasks no longer surface.

    In-flight work keeps the same branch tag while it runs, so only settled runs are purged; a
    running run is left untouched. Cleanup is best-effort and follows the committed deletion.
    """
    branch_name = f"task-leak-branch-{uuid4()}"
    branch_tag = WorkflowTag.BRANCH.render(identifier=branch_name)

    settled_run = await prefect_client.create_flow_run(
        flow=_noop_flow, tags=[TAG_NAMESPACE, branch_tag], state=State(type=StateType.COMPLETED)
    )
    running_run = await prefect_client.create_flow_run(
        flow=_noop_flow, tags=[TAG_NAMESPACE, branch_tag], state=State(type=StateType.RUNNING)
    )

    await purge_deleted_branch_tasks(branch_name=branch_name)

    adapter = PrefectClientAdapter(client=prefect_client)
    settled_after = await adapter.read_flow_runs(
        flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[settled_run.id]))
    )
    running_after = await adapter.read_flow_runs(
        flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[running_run.id]))
    )

    assert settled_after == []
    assert [run.id for run in running_after] == [running_run.id]


async def test_purge_keeps_the_task_that_deleted_the_branch(prefect_client: PrefectClient) -> None:
    """The deleting task survives its own cleanup, so a caller still waiting on it can read it."""
    branch_name = f"task-leak-branch-{uuid4()}"
    branch_tag = WorkflowTag.BRANCH.render(identifier=branch_name)

    deletion_run = await prefect_client.create_flow_run(
        flow=_noop_flow, tags=[TAG_NAMESPACE, branch_tag], state=State(type=StateType.COMPLETED)
    )
    other_run = await prefect_client.create_flow_run(
        flow=_noop_flow, tags=[TAG_NAMESPACE, branch_tag], state=State(type=StateType.COMPLETED)
    )

    await purge_deleted_branch_tasks(branch_name=branch_name, deletion_task_id=str(deletion_run.id))

    adapter = PrefectClientAdapter(client=prefect_client)
    deletion_after = await adapter.read_flow_runs(
        flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[deletion_run.id]))
    )
    other_after = await adapter.read_flow_runs(flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[other_run.id])))

    assert [run.id for run in deletion_after] == [deletion_run.id]
    assert other_after == []
