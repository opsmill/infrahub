from graphene import Field, List, ObjectType, String


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
