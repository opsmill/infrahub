from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from graphene import Boolean, Field, InputObjectType, Mutation, String
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import FlowFilter, FlowFilterId, FlowRunFilter, FlowRunFilterId
from prefect.client.schemas.objects import State, StateType

from infrahub.core import registry
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import PermissionAction, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.exceptions import ValidationError
from infrahub.graphql.queries.task_actions import UNSUPPORTED_ACTION_REASON, TaskActionGenerator
from infrahub.graphql.types.task import TaskActionType, TaskInfo
from infrahub.proposed_change.artifact_task_retry import (
    ArtifactDefinitionTaskRetryResolver,
    ArtifactTargetTaskRetryResolver,
)
from infrahub.proposed_change.check_run import CheckRunRequestBuilder
from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter
from infrahub.utils import extract_camelcase_words
from infrahub.workflows.catalogue import REQUEST_PROPOSED_CHANGE_PIPELINE, WEBHOOK_SEND
from infrahub.workflows.constants import WorkflowTag

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.context import InfrahubContext
    from infrahub.graphql.initialization import GraphqlContext
    from infrahub.permissions.manager import PermissionManager
    from infrahub.proposed_change.artifact_task_retry import ArtifactTaskRetryResolver
    from infrahub.services.adapters.workflow import InfrahubWorkflow
    from infrahub.task_manager.flow_run.prefect_client import ReaderPrefectClient
    from infrahub.workflows.models import WorkflowInfo


class TaskActionInput(InputObjectType):
    id = String(required=True)


@dataclass(frozen=True)
class DeliveryRun:
    """A delivery's identity and frozen parameters, as needed to act on it."""

    workflow_name: str | None
    state_type: StateType | None
    branch_name: str | None
    parameters: dict[str, Any]


class DeliveryReader:
    """Loads a delivery run through a query-only Prefect client; it cannot change or delete runs."""

    def __init__(self, client: ReaderPrefectClient) -> None:
        self.client = client

    async def read(self, task_id: str) -> DeliveryRun:
        """Return the delivery's workflow, state, and frozen parameters.

        Raises:
            ValidationError: When the id is malformed or the delivery has aged out of retention.

        """
        try:
            flow_run_id = UUID(task_id)
        except ValueError:
            raise ValidationError(input_value="This delivery is no longer available.") from None
        runs = await self.client.read_flow_runs(flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[flow_run_id])))
        run = runs[0] if runs else None
        if run is None:
            raise ValidationError(input_value="This delivery is no longer available.")

        flows = await self.client.read_flows(flow_filter=FlowFilter(id=FlowFilterId(any_=[run.flow_id])))
        workflow_name = flows[0].name if flows else None
        branch_name = run.parameters.get("branch_name")
        return DeliveryRun(
            workflow_name=workflow_name,
            state_type=run.state_type,
            branch_name=str(branch_name) if branch_name is not None else None,
            parameters=run.parameters,
        )


class DeliveryActionAuthorizer:
    """Decides whether a recovery action is allowed on a delivery, raising when it is not.

    The required permission is evaluated against the branch the authorizer is scoped to.
    """

    def __init__(
        self,
        action_generator: TaskActionGenerator,
        permissions: PermissionManager,
        branch_name: str,
        default_branch_name: str,
    ) -> None:
        self.action_generator = action_generator
        self.permissions = permissions
        self.branch_name = branch_name
        self.default_branch_name = default_branch_name

    def authorize(self, delivery: DeliveryRun, action: TaskActionType) -> None:
        """Authorize the action on the delivery.

        Raises:
            ValidationError: When the action does not apply to the delivery's current state.

        """
        self.action_generator.require_available(
            workflow_name=delivery.workflow_name, state_type=delivery.state_type, action=action
        )

        namespace, *name_parts = extract_camelcase_words(str(delivery.parameters["webhook_kind"]))
        on_default_branch = self.branch_name == self.default_branch_name
        self.permissions.raise_for_permission(
            permission=ObjectPermission(
                namespace=namespace,
                name="".join(name_parts),
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_DEFAULT.value
                if on_default_branch
                else PermissionDecision.ALLOW_OTHER.value,
            )
        )


def resolve_delivery_branch_name(delivery: DeliveryRun, default_branch_name: str) -> str:
    """Return the branch acting on the delivery affects.

    Actions follow the branch the delivery was initiated from, not the branch the request was made
    on. A delivery without a branch belongs to the default branch.
    """
    return delivery.branch_name or default_branch_name


def build_delivery_action_authorizer(
    graphql_context: GraphqlContext, delivery: DeliveryRun
) -> DeliveryActionAuthorizer:
    return DeliveryActionAuthorizer(
        action_generator=TaskActionGenerator(),
        permissions=graphql_context.active_permissions,
        branch_name=resolve_delivery_branch_name(delivery=delivery, default_branch_name=registry.default_branch),
        default_branch_name=registry.default_branch,
    )


class TaskRetryHandler(ABC):
    """Authorizes and submits the retry of the task runs of one type."""

    @abstractmethod
    def supports(self, run: DeliveryRun) -> bool: ...

    @abstractmethod
    async def retry(self, run: DeliveryRun) -> WorkflowInfo | None:
        """Submit the retry of the run.

        Returns:
            The run that the task history lists for the retry, or None when it lists none.

        Raises:
            ValidationError: When the run has nothing left to retry, or what it ran can no longer run.
            PermissionDeniedError: When the account is not allowed to retry the run.

        """


class DeliveryRetryHandler(TaskRetryHandler):
    """Replays a settled webhook delivery, with its frozen payload, as a new and independent delivery."""

    def __init__(
        self, authorizer: DeliveryActionAuthorizer, workflow: InfrahubWorkflow, context: InfrahubContext
    ) -> None:
        self.authorizer = authorizer
        self.workflow = workflow
        self.context = context

    def supports(self, run: DeliveryRun) -> bool:
        return run.workflow_name == WEBHOOK_SEND.name

    async def retry(self, run: DeliveryRun) -> WorkflowInfo | None:
        self.authorizer.authorize(delivery=run, action=TaskActionType.RETRY)

        webhook_id = run.parameters["webhook_id"]
        return await self.workflow.submit_workflow(
            workflow=WEBHOOK_SEND,
            context=self.context,
            parameters={
                "webhook_id": webhook_id,
                "webhook_kind": run.parameters["webhook_kind"],
                "webhook_name": run.parameters["webhook_name"],
                "payload": run.parameters["payload"],
                "branch_name": run.branch_name,
            },
            tags=[WorkflowTag.RELATED_NODE.render(identifier=webhook_id)],
        )


class ArtifactCheckRetryHandler(TaskRetryHandler):
    """Retries what a finished artifact check task left failed or unfinished, as a new run of the checks.

    The retry never replays the parameters stored with the run: it requests the artifact checks of the proposed
    change again, so it reads the current repository commit and updates the conclusion of the validator. The
    task history does not list the run that takes the request, so the retry returns no run.
    """

    def __init__(
        self,
        resolver: ArtifactTaskRetryResolver,
        request_builder: CheckRunRequestBuilder,
        workflow: InfrahubWorkflow,
        context: InfrahubContext,
    ) -> None:
        self.resolver = resolver
        self.request_builder = request_builder
        self.workflow = workflow
        self.context = context

    def supports(self, run: DeliveryRun) -> bool:
        return run.workflow_name == self.resolver.workflow_name

    async def retry(self, run: DeliveryRun) -> WorkflowInfo | None:
        request = await self.resolver.resolve(parameters=run.parameters)
        pipeline_request = await self.request_builder.build(request=request)
        await self.workflow.submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_PIPELINE,
            parameters={"model": pipeline_request},
            context=self.context,
        )
        return None


class TaskRetryDispatcher:
    """Retries a task run through the handler of its type."""

    def __init__(self, action_generator: TaskActionGenerator, handlers: list[TaskRetryHandler]) -> None:
        self.action_generator = action_generator
        self.handlers = handlers

    async def retry(self, run: DeliveryRun) -> WorkflowInfo | None:
        """Submit the retry of the run.

        Returns:
            The run that the task history lists for the retry, or None when it lists none.

        Raises:
            ValidationError: When retry does not apply to the type or the current state of the run, or the
                handler of its type refuses it.
            PermissionDeniedError: When the account is not allowed to retry the run.

        """
        self.action_generator.require_available(
            workflow_name=run.workflow_name, state_type=run.state_type, action=TaskActionType.RETRY
        )
        for handler in self.handlers:
            if handler.supports(run=run):
                return await handler.retry(run=run)
        raise ValidationError(input_value=f"Retry is unavailable: {UNSUPPORTED_ACTION_REASON}.")


def build_task_retry_dispatcher(graphql_context: GraphqlContext, run: DeliveryRun) -> TaskRetryDispatcher:
    workflow = graphql_context.active_service.workflow
    context = graphql_context.get_context()
    request_builder = CheckRunRequestBuilder(db=graphql_context.db, node_manager=NodeManager)
    return TaskRetryDispatcher(
        action_generator=TaskActionGenerator(),
        handlers=[
            DeliveryRetryHandler(
                authorizer=build_delivery_action_authorizer(graphql_context=graphql_context, delivery=run),
                workflow=workflow,
                context=context,
            ),
            ArtifactCheckRetryHandler(
                resolver=ArtifactTargetTaskRetryResolver(db=graphql_context.db, node_manager=NodeManager),
                request_builder=request_builder,
                workflow=workflow,
                context=context,
            ),
            ArtifactCheckRetryHandler(
                resolver=ArtifactDefinitionTaskRetryResolver(db=graphql_context.db, node_manager=NodeManager),
                request_builder=request_builder,
                workflow=workflow,
                context=context,
            ),
        ],
    )


class InfrahubTaskRetry(Mutation):
    """Retry a settled webhook delivery, or the failed and unfinished checks of a finished artifact check task."""

    class Arguments:
        data = TaskActionInput(required=True)

    ok = Boolean()
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: TaskActionInput) -> InfrahubTaskRetry:  # noqa: ARG003
        graphql_context: GraphqlContext = info.context

        async with get_client(sync_client=False) as client:
            run = await DeliveryReader(PrefectClientAdapter(client)).read(str(data.id))

        dispatcher = build_task_retry_dispatcher(graphql_context=graphql_context, run=run)
        workflow = await dispatcher.retry(run=run)
        return cls(ok=True, task={"id": workflow.id} if workflow is not None else None)


class InfrahubTaskCancel(Mutation):
    """Cancel an in-flight delivery, stopping any remaining retries without recalling a sent request."""

    class Arguments:
        data = TaskActionInput(required=True)

    ok = Boolean()
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: TaskActionInput) -> InfrahubTaskCancel:  # noqa: ARG003
        graphql_context: GraphqlContext = info.context

        async with get_client(sync_client=False) as client:
            prefect = PrefectClientAdapter(client)
            delivery = await DeliveryReader(prefect).read(str(data.id))
            build_delivery_action_authorizer(graphql_context, delivery).authorize(delivery, TaskActionType.CANCEL)
            resulting_state = await prefect.set_flow_run_state(
                flow_run_id=UUID(str(data.id)), state=State(type=StateType.CANCELLING), force=False
            )
        if resulting_state not in {StateType.CANCELLING, StateType.CANCELLED}:
            raise ValidationError(input_value="This delivery settled before it could be cancelled.")
        return cls(ok=True, task={"id": str(data.id)})
