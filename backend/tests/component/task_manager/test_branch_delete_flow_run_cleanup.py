from uuid import uuid4

from fast_depends import Provider
from prefect import flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId
from prefect.states import Completed
from tests.adapters.workflow import WorkflowRecorder

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import delete_branch
from infrahub.core.initialization import create_branch
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.task_manager.flow_run.filters import FlowRunFilterBuilder
from infrahub.task_manager.flow_run.models import FlowRunQueryCriteria
from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter
from infrahub.workers.dependencies import build_database
from infrahub.workflows.constants import TAG_NAMESPACE, WorkflowTag


@flow
def _noop_flow() -> None:
    """A trivial flow used only to create a branch-tagged flow run standing in for a task."""


async def test_deleting_a_branch_removes_its_task_history(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    workflow_recorder: WorkflowRecorder,
    dependency_provider: Provider,
    prefect_client: PrefectClient,
) -> None:
    """A branch's flow runs must not outlive the branch, so a same-named branch starts with no tasks.

    Tasks are Prefect flow runs associated with a branch by a name-based tag. When a branch is
    deleted and later recreated with the same name, the recreated branch would otherwise retrieve
    the old branch's flow runs, since both share the tag.
    """
    branch_name = "task-leak-branch"
    await create_branch(db=db, branch_name=branch_name)

    branch_tag = WorkflowTag.BRANCH.render(identifier=branch_name)
    old_run = await prefect_client.create_flow_run(flow=_noop_flow, tags=[TAG_NAMESPACE, branch_tag], state=Completed())

    adapter = PrefectClientAdapter(client=prefect_client)
    branch_filter = FlowRunFilterBuilder().build_flow_run_filter(criteria=FlowRunQueryCriteria(branch=branch_name))

    runs_before = await adapter.read_flow_runs(flow_run_filter=branch_filter)
    assert [run.id for run in runs_before] == [old_run.id]

    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )
    with dependency_provider.scope(build_database, lambda singleton=True: db):  # noqa: ARG005
        await delete_branch(branch=branch_name, context=context)

    old_run_after = await adapter.read_flow_runs(flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[old_run.id])))
    assert old_run_after == []
