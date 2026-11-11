from uuid import uuid4

from fast_depends import Provider
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId
from prefect.client.schemas.objects import State, StateType

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.branch.tasks import purge_deleted_branch_tasks
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import delete_branch
from infrahub.core.initialization import create_branch
from infrahub.database import InfrahubDatabase
from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter
from infrahub.workers.dependencies import build_database
from infrahub.workflows.constants import TAG_NAMESPACE, WorkflowTag
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.dependency_override import override_dependency


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


async def test_purge_leaves_the_run_that_deleted_the_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    dependency_provider: Provider,
    workflow_recorder: WorkflowRecorder,
    prefect_client: PrefectClient,
) -> None:
    """A caller waits on the deletion's run until it settles, so the purge the deletion triggers must not remove it."""
    branch = await create_branch(db=db, branch_name=f"purge-deleting-run-{uuid4().hex[:8]}")
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )
    with override_dependency(build_database, lambda singleton=True: db, dependency_provider=dependency_provider):  # noqa: ARG005
        deletion = await delete_branch(branch=branch.name, context=context, return_state=True)
    deletion_run_id = deletion.state_details.flow_run_id

    await purge_deleted_branch_tasks(branch_name=branch.name)

    adapter = PrefectClientAdapter(client=prefect_client)
    remaining = await adapter.read_flow_runs(flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[deletion_run_id])))
    assert (deletion.type, [run.id for run in remaining]) == (StateType.COMPLETED, [deletion_run_id])
