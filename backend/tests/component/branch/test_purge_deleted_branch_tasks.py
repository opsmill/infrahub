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
