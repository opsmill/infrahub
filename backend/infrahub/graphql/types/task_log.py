from graphene import Field, InputObjectType, List, ObjectType, String
from graphene.types.uuid import UUID

from .enums import Severity


class RelatedTaskLogCreateInput(InputObjectType):
    message = String(required=True)
    severity = Severity(required=True)


class TaskLogCreateInput(RelatedTaskLogCreateInput):
    task_id = UUID(required=True)


class TaskLog(ObjectType):
    message = String(required=True)
    severity = String(required=True)
    task_id = String(required=True)
    timestamp = String(required=True)
    id = String(required=False)


class TaskLogNodes(ObjectType):
    node = Field(TaskLog)


class TaskLogEdge(ObjectType):
    edges = List(TaskLogNodes)
