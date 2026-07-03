from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from graphene import Boolean, Enum, Field, Float, Int, Interface, List, NonNull, ObjectType, String
from graphene.types.generic import GenericScalar
from prefect.client.schemas.objects import StateType

from infrahub.workflows.catalogue import WEBHOOK_SEND

from .task_log import TaskLogEdge

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

TaskState = Enum.from_enum(StateType)


class TaskActionType(StrEnum):
    """Recovery actions a task run can expose."""

    RETRY = "RETRY"
    CANCEL = "CANCEL"


TaskActionName = Enum.from_enum(TaskActionType)


class TaskAction(ObjectType):
    action = TaskActionName(required=True)
    available = Boolean(required=True)
    unavailability_reason = String(required=False)


class TaskInfo(ObjectType):
    id = Field(String)


class HttpRequest(ObjectType):
    url = String(required=True)
    headers = GenericScalar(required=True, description="Request headers as sent, with secret values masked")


class HttpResponse(ObjectType):
    status_code = Int(required=False)
    body = String(required=False)
    latency_ms = Float(required=False)


class DeliveryError(ObjectType):
    status_class = String(required=True)
    message = String(required=True)
    remediation = String(required=True)


class TaskRelatedNode(ObjectType):
    id = String(required=True)
    kind = String(required=True)


class TaskNodeInterface(Interface):
    """Fields shared by every task run; concrete types are discriminated by the run's workflow name."""

    id = String(required=True)
    title = String(required=True)
    conclusion = String(required=True)
    state = TaskState(required=False)
    progress = Float(required=False)
    workflow = String(required=False)
    branch = String(required=False)
    created_at = String(required=True)
    updated_at = String(required=True)
    parameters = GenericScalar(required=False)
    tags = List(String, required=False)
    start_time = String(required=False)
    related_node = String(
        required=False,
        deprecation_reason="This field is deprecated and it will be removed in a future release, use related_nodes instead",
    )
    related_node_kind = String(
        required=False,
        deprecation_reason="This field is deprecated and it will be removed in a future release, use related_nodes instead",
    )
    related_nodes = List(TaskRelatedNode)
    logs = Field(TaskLogEdge)
    available_actions = List(NonNull(TaskAction), required=True)

    @classmethod
    def resolve_type(
        cls,
        instance: dict[str, Any],
        info: GraphQLResolveInfo,  # noqa: ARG003
    ) -> type[ObjectType]:
        return TASK_TYPES.get(instance.get("workflow", ""), TaskNode)


class TaskNode(ObjectType):
    class Meta:
        interfaces = (TaskNodeInterface,)


class WebhookDeliveryTask(ObjectType):
    class Meta:
        interfaces = (TaskNodeInterface,)

    http_request = Field(HttpRequest, required=False)
    http_response = Field(HttpResponse, required=False)
    error = Field(DeliveryError, required=False)


TASK_TYPES: dict[str, type[ObjectType]] = {
    WEBHOOK_SEND.name: WebhookDeliveryTask,
    "undefined": TaskNode,
}


class TaskNodes(ObjectType):
    node = Field(TaskNodeInterface)
