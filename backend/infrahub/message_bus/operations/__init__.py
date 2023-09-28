import json

from infrahub.log import get_logger
from infrahub.message_bus import InfrahubResponse, messages
from infrahub.message_bus.operations import (
    check,
    event,
    finalize,
    git,
    refresh,
    requests,
    transform,
)
from infrahub.message_bus.types import MessageTTL
from infrahub.services import InfrahubServices

log = get_logger()

COMMAND_MAP = {
    "check.repository.check_definition": check.repository.check_definition,
    "check.repository.merge_conflicts": check.repository.merge_conflicts,
    "event.branch.create": event.branch.create,
    "event.schema.update": event.schema.update,
    "finalize.validator.execution": finalize.validator.execution,
    "git.branch.create": git.branch.create,
    "git.file.get": git.file.get,
    "refresh.registry.branches": refresh.registry.branches,
    "request.git.create_branch": requests.git.create_branch,
    "request.artifact_definition.generate": requests.artifact_definition.generate,
    "request.proposed_change.data_integrity": requests.proposed_change.data_integrity,
    "request.proposed_change.refresh_artifacts": requests.proposed_change.refresh_artifacts,
    "request.proposed_change.repository_checks": requests.proposed_change.repository_checks,
    "request.proposed_change.schema_integrity": requests.proposed_change.schema_integrity,
    "request.repository.checks": requests.repository.check,
    "transform.jinja.template": transform.jinja.template,
    "transform.python.data": transform.python.data,
}


async def execute_message(routing_key: str, message_body: bytes, service: InfrahubServices):
    message_data = json.loads(message_body)
    message = messages.MESSAGE_MAP[routing_key](**message_data)
    message.set_log_data(routing_key=routing_key)
    try:
        await COMMAND_MAP[routing_key](message=message, service=service)
    except Exception as exc:  # pylint: disable=broad-except
        if message.reply_requested:
            response = InfrahubResponse(passed=False, response_class="rpc_error", response_data={"error": str(exc)})
            await service.reply(message=response, initiator=message)
            return
        if message.reached_max_retries:
            log.error("Message failed after maximum number of retries", error=str(exc))
            return
        message.increase_retry_count()
        await service.send(message, delay=MessageTTL.FIVE)
