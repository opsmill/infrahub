from infrahub.core.constants import TaskConclusion
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices


async def result(message: messages.LogTaskResult, service: InfrahubServices) -> None:
    conclusion = TaskConclusion.from_bool(message.success).upper()
    created_by = ""
    if message.account_id:
        created_by = f'created_by "{message.account_id}",'
    query = """
    mutation MyMutation(
        $conclusion: TaskConclusion!,
        $message: String!,
        $related_node: String!,
        $severity: Severity!,
        $task_id: UUID!,
        $title: String!
        ) {
        TaskCreate(
            data: {
                id: $task_id,
                title: $title,
                conclusion: $conclusion,
                %(created_by)s
                related_node: $related_node
            }
        ) {
            ok
        }
        LogCreate(
            data: {
                message: $message,
                severity: $severity,
                task_id: $task_id
            }
        ) {
            ok
        }
    }
    """ % {
        "created_by": created_by,
    }
    await service.client.execute_graphql(
        query=query,
        variables={
            "conclusion": conclusion,
            "message": message.message,
            "related_node": message.related_node,
            "severity": message.severity.upper(),
            "task_id": message.task_id,
            "title": message.title,
        },
    )
