import json

from infrahub.message_bus import messages
from infrahub.message_bus.operations import check, requests
from infrahub.services import InfrahubServices

COMMAND_MAP = {
    "check.repository.merge_conflicts": check.repository.merge_conflicts,
    "request.artifact_definition.generate": requests.artifact_definition.generate,
    "request.proposed_change.data_integrity": requests.proposed_change.data_integrity,
    "request.proposed_change.refresh_artifacts": requests.proposed_change.refresh_artifacts,
    "request.proposed_change.repository_checks": requests.proposed_change.repository_checks,
    "request.proposed_change.schema_integrity": requests.proposed_change.schema_integrity,
    "request.repository.checks": requests.repository.check,
}


async def execute_message(routing_key: str, message_body: bytes, service: InfrahubServices):
    message_data = json.loads(message_body)
    message = messages.MESSAGE_MAP[routing_key](**message_data)
    message.set_log_data(routing_key=routing_key)
    await COMMAND_MAP[routing_key](message=message, service=service)
