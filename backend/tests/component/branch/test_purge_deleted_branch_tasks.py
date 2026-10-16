from uuid import UUID, uuid4

from prefect import flow, get_client, tags
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId
from prefect.client.schemas.objects import State, StateType
from prefect.events.related import related_resources_from_run_context
from prefect.events.schemas.events import Event, RelatedResource
from prefect.runtime import flow_run
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.utilities.schema_tools.hydration import HydrationContext, hydrate

from infrahub.branch.tasks import purge_deleted_branch_tasks
from infrahub.branch.triggers import TRIGGER_BRANCH_DELETED_PURGE_TASKS
from infrahub.events.branch_action import BranchDeletedEvent
from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter
from infrahub.workflows.constants import TAG_NAMESPACE, WorkflowTag


@flow
def _noop_flow() -> None:
    """A trivial flow used only to create branch-tagged flow runs standing in for tasks."""


@flow
async def _deleting_flow() -> tuple[UUID, list[RelatedResource]]:
    """Stand in for the branch delete flow: its run, and what an event it emits says about that run."""
    async with get_client() as client:
        return UUID(flow_run.id), await related_resources_from_run_context(client=client)


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


async def test_purge_keeps_the_settled_run_of_the_flow_that_deleted_the_branch(
    prefect_client: PrefectClient,
) -> None:
    """The run that emitted the deletion event survives the purge that the event triggers.

    The caller of a branch delete polls that run until it reads the final state, and the purge can
    finish between the end of the run and the last poll.
    """
    branch_name = f"task-leak-branch-{uuid4()}"
    branch_tag = WorkflowTag.BRANCH.render(identifier=branch_name)

    with tags(TAG_NAMESPACE, branch_tag):
        deleting_run_id, run_context = await _deleting_flow()
    settled_run = await prefect_client.create_flow_run(
        flow=_noop_flow, tags=[TAG_NAMESPACE, branch_tag], state=State(type=StateType.COMPLETED)
    )
    emitted = Event(
        event=BranchDeletedEvent.event_name,
        resource={"prefect.resource.id": f"infrahub.branch.{branch_name}"},
        related=run_context,
        payload={"data": {"branch_name": branch_name}},
    )
    event = ReceivedEvent.model_validate(emitted.model_dump())
    parameters = hydrate(
        TRIGGER_BRANCH_DELETED_PURGE_TASKS.actions[0].parameters,
        HydrationContext(render_jinja=True, jinja_context={"event": event}, raise_on_error=True),
    )

    await purge_deleted_branch_tasks(
        branch_name=parameters["branch_name"], deleting_flow_run_id=parameters["deleting_flow_run_id"]
    )

    deleting_run = await prefect_client.read_flow_run(flow_run_id=deleting_run_id)
    adapter = PrefectClientAdapter(client=prefect_client)
    settled_after = await adapter.read_flow_runs(
        flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[settled_run.id]))
    )

    assert deleting_run.state_type == StateType.COMPLETED
    assert settled_after == []
