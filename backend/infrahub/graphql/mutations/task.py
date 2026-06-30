from __future__ import annotations

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
from infrahub.exceptions import ValidationError
from infrahub.graphql.queries.task_actions import TaskActionGenerator
from infrahub.graphql.types.task import TaskActionType, TaskInfo
from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter
from infrahub.workflows.catalogue import WEBHOOK_SEND

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.graphql.initialization import GraphqlContext
    from infrahub.permissions.manager import PermissionManager
    from infrahub.task_manager.flow_run.prefect_client import ReaderPrefectClient


class TaskActionInput(InputObjectType):
    id = String(required=True)


@dataclass(frozen=True)
class DeliveryRun:
    """A delivery's identity and frozen parameters, as needed to act on it."""

    workflow_name: str | None
    state_type: StateType | None
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
        return DeliveryRun(workflow_name=workflow_name, state_type=run.state_type, parameters=run.parameters)


class DeliveryActionAuthorizer:
    """Decides whether a recovery action is allowed on a delivery, raising when it is not."""

    def __init__(self, action_generator: TaskActionGenerator, permissions: PermissionManager, branch: Branch) -> None:
        self.action_generator = action_generator
        self.permissions = permissions
        self.branch = branch

    def authorize(self, delivery: DeliveryRun, action: TaskActionType) -> None:
        """Authorize the action on the delivery.

        Raises:
            ValidationError: When the action does not apply to the delivery's current state.

        """
        actions = self.action_generator.generate(delivery.workflow_name, delivery.state_type)
        searched_action = next((entry for entry in actions if entry.action == action), None)
        if searched_action is None or not searched_action.available:
            reason = searched_action.unavailability_reason if searched_action else "it is not supported for this task"
            raise ValidationError(input_value=f"{action.value.capitalize()} is unavailable: {reason}.")

        webhook_schema = registry.schema.get_node_schema(
            name=str(delivery.parameters["webhook_kind"]), branch=self.branch.name, duplicate=False
        )
        self.permissions.raise_for_permission(
            permission=ObjectPermission(
                namespace=webhook_schema.namespace,
                name=webhook_schema.name,
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_DEFAULT.value
                if self.branch.name == registry.default_branch
                else PermissionDecision.ALLOW_OTHER.value,
            )
        )


def build_delivery_action_authorizer(graphql_context: GraphqlContext) -> DeliveryActionAuthorizer:
    return DeliveryActionAuthorizer(
        action_generator=TaskActionGenerator(),
        permissions=graphql_context.active_permissions,
        branch=graphql_context.branch,
    )


class InfrahubTaskRetry(Mutation):
    """Retry a settled delivery by replaying its frozen payload as a new, independent delivery."""

    class Arguments:
        data = TaskActionInput(required=True)

    ok = Boolean()
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: TaskActionInput) -> InfrahubTaskRetry:  # noqa: ARG003
        graphql_context: GraphqlContext = info.context

        async with get_client(sync_client=False) as client:
            delivery = await DeliveryReader(PrefectClientAdapter(client)).read(str(data.id))

        build_delivery_action_authorizer(graphql_context).authorize(delivery, TaskActionType.RETRY)

        workflow = await graphql_context.active_service.workflow.submit_workflow(
            workflow=WEBHOOK_SEND,
            context=graphql_context.get_context(),
            parameters={
                "webhook_id": delivery.parameters["webhook_id"],
                "webhook_kind": delivery.parameters["webhook_kind"],
                "webhook_name": delivery.parameters["webhook_name"],
                "payload": delivery.parameters["payload"],
                "branch_name": delivery.parameters.get("branch_name"),
            },
        )
        return cls(ok=True, task={"id": workflow.id})


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
            build_delivery_action_authorizer(graphql_context).authorize(delivery, TaskActionType.CANCEL)
            await prefect.set_flow_run_state(
                flow_run_id=UUID(str(data.id)), state=State(type=StateType.CANCELLING), force=False
            )
        return cls(ok=True, task={"id": str(data.id)})
