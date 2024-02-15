from __future__ import annotations

from graphene import Field, ObjectType, String

from .task_log import TaskLogEdge


class Task(ObjectType):
    id = String(required=True)
    title = String(required=True)
    conclusion = String(required=True)
    created_at = String(required=True)
    updated_at = String(required=True)


class TaskNode(Task):
    related_node = String(required=True)
    related_node_kind = String(required=True)
    logs = Field(TaskLogEdge)


class TaskNodes(ObjectType):
    node = Field(TaskNode)
