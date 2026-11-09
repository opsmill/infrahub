from prefect import flow

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workflows.constants import WorkflowPriority
from infrahub.workflows.models import WorkflowDefinition

RECORDED_CONTEXTS: list[InfrahubContext] = []


@flow(name="context-probe")
async def context_probe(context: InfrahubContext) -> InfrahubContext:
    return context


@flow(name="context-recorder")
async def context_recorder(context: InfrahubContext) -> None:
    RECORDED_CONTEXTS.append(context)


CONTEXT_PROBE = WorkflowDefinition(
    name="context_probe",
    module="tests.unit.services.adapters.workflow.test_local_stamping",
    function="context_probe",
)

CONTEXT_PROBE_HIGH_DEFAULT = WorkflowDefinition(
    name="context_probe_high_default",
    module="tests.unit.services.adapters.workflow.test_local_stamping",
    function="context_probe",
    default_priority=WorkflowPriority.HIGH,
)

CONTEXT_RECORDER = WorkflowDefinition(
    name="context_recorder",
    module="tests.unit.services.adapters.workflow.test_local_stamping",
    function="context_recorder",
)


def build_context(priority: WorkflowPriority | None = None) -> InfrahubContext:
    return InfrahubContext(
        branch=BranchContext(name="main", id="1111aaaa-0000-0000-0000-000000000000"),
        account=AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id="account-a"),
        priority=priority,
    )


class TestLocalExecutionStamping:
    async def test_explicit_priority_is_stamped_into_injected_context(self) -> None:
        service = WorkflowLocalExecution()
        caller_context = build_context(priority=None)

        received_context = await service.execute_workflow(
            workflow=CONTEXT_PROBE,
            expected_return=InfrahubContext,
            context=caller_context,
            priority=WorkflowPriority.HIGH,
        )

        assert received_context.priority is WorkflowPriority.HIGH
        assert caller_context.priority is None

    async def test_context_priority_is_stamped_when_no_explicit_priority(self) -> None:
        service = WorkflowLocalExecution()
        caller_context = build_context(priority=WorkflowPriority.LOW)

        received_context = await service.execute_workflow(
            workflow=CONTEXT_PROBE_HIGH_DEFAULT,
            expected_return=InfrahubContext,
            context=caller_context,
        )

        assert received_context.priority is WorkflowPriority.LOW
        assert caller_context.priority is WorkflowPriority.LOW

    async def test_catalogue_default_is_stamped_without_mutating_caller(self) -> None:
        service = WorkflowLocalExecution()
        caller_context = build_context(priority=None)

        received_context = await service.execute_workflow(
            workflow=CONTEXT_PROBE,
            expected_return=InfrahubContext,
            context=caller_context,
        )

        assert received_context.priority is WorkflowPriority.MEDIUM
        assert caller_context.priority is None

    async def test_submit_workflow_stamps_context_priority(self) -> None:
        service = WorkflowLocalExecution()
        caller_context = build_context(priority=None)
        RECORDED_CONTEXTS.clear()

        await service.submit_workflow(
            workflow=CONTEXT_RECORDER,
            context=caller_context,
            priority=WorkflowPriority.LOW,
        )

        assert len(RECORDED_CONTEXTS) == 1
        assert RECORDED_CONTEXTS[0].priority is WorkflowPriority.LOW
        assert caller_context.priority is None
