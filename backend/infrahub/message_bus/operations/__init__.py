import json

from infrahub.message_bus import messages
from infrahub.message_bus.operations import requests
from infrahub.services import InfrahubServices

COMMAND_MAP = {
    "request.proposed_change.repository_checks": requests.proposed_change.repository_checks,
    "request.repository.checks": requests.repository.check,
}


async def execute_message(routing_key: str, message_body: bytes, service: InfrahubServices):
    message_data = json.loads(message_body)
    message = messages.MESSAGE_MAP[routing_key](**message_data)
    await COMMAND_MAP[routing_key](message=message, service=service)
