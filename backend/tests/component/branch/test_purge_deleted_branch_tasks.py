from uuid import uuid4

from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import State, StateType

from infrahub.branch.tasks import purge_deleted_branch_tasks
from infrahub.task_manager.flow_run.filters import FlowRunFilterBuilder
from infrahub.task_manager.flow_run.models import FlowRunQueryCriteria
from infrahub.workflows.constants import TAG_NAMESPACE, WorkflowTag


@flow
def _noop_flow() -> None:
    """A trivial flow used only to create branch-tagged flow runs standing in for tasks."""


async def test_purge_detaches_settled_runs_of_a_deleted_branch_but_leaves_running_ones(
    prefect_client: PrefectClient,
) -> None:
    """A deleted branch's settled runs stay readable by id but no longer list under its name.

    A caller that started a run on the branch keeps reading that run by id until it is final, so
    the purge must not make the id unreadable; a branch re-created with the same name must still
    list none of the old branch's settled runs, and in-flight work keeps its branch tag.
    """
    branch_name = f"task-leak-branch-{uuid4()}"
    branch_id = str(uuid4())
    branch_tag = WorkflowTag.BRANCH.render(identifier=branch_name)

    settled_run = await prefect_client.create_flow_run(
        flow=_noop_flow, tags=[TAG_NAMESPACE, branch_tag], state=State(type=StateType.COMPLETED)
    )
    running_run = await prefect_client.create_flow_run(
        flow=_noop_flow, tags=[TAG_NAMESPACE, branch_tag], state=State(type=StateType.RUNNING)
    )

    await purge_deleted_branch_tasks(branch_name=branch_name, branch_id=branch_id)

    settled_after = await prefect_client.read_flow_run(settled_run.id)
    running_after = await prefect_client.read_flow_run(running_run.id)
    branch_runs = await prefect_client.read_flow_runs(
        flow_run_filter=FlowRunFilterBuilder().build_flow_run_filter(FlowRunQueryCriteria(branch=branch_name))
    )

    assert settled_after.id == settled_run.id
    assert sorted(settled_after.tags) == sorted(
        [
            "infrahub.app",
            f"infrahub.app/deleted-branch/{branch_name}",
            f"infrahub.app/deleted-branch-id/{branch_id}",
        ]
    )
    assert sorted(running_after.tags) == sorted(["infrahub.app", f"infrahub.app/branch/{branch_name}"])
    assert [run.id for run in branch_runs] == [running_run.id]
