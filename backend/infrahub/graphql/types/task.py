from __future__ import annotations

from enum import StrEnum

from graphene import Boolean, Enum, Field, Float, List, NonNull, ObjectType, String
from graphene.types.generic import GenericScalar
from prefect.client.schemas.objects import StateType

from .task_log import TaskLogEdge

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


class Task(ObjectType):
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


class TaskRelatedNode(ObjectType):
    id = String(required=True)
    kind = String(required=True)


class TaskNode(Task):
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


class TaskNodes(ObjectType):
    node = Field(TaskNode)
