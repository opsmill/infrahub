from aio_pika.abc import AbstractIncomingMessage

from infrahub.log import clear_log_context, get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.operations import execute_message
from infrahub.services import InfrahubServices

log = get_logger()


class WorkerCallback:
    def __init__(self, service: InfrahubServices) -> None:
        self.service = service

    async def run_command(self, message: AbstractIncomingMessage) -> None:
        clear_log_context()
        if message.routing_key in messages.MESSAGE_MAP:
            await execute_message(routing_key=message.routing_key, message_body=message.body, service=self.service)
