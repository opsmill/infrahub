import ujson
from prefect import Flow

from infrahub.message_bus import RPCErrorResponse, messages
from infrahub.message_bus.operations import (
    check,
    event,
    finalize,
    git,
    refresh,
    requests,
    send,
)
from infrahub.message_bus.types import MessageTTL
from infrahub.services import InfrahubServices
from infrahub.tasks.check import set_check_status

COMMAND_MAP = {
    "check.generator.run": check.generator.run,
    "event.branch.merge": event.branch.merge,
    "finalize.validator.execution": finalize.validator.execution,
    "git.file.get": git.file.get,
    "git.repository.connectivity": git.repository.connectivity,
    "refresh.git.fetch": git.repository.fetch,
    "refresh.registry.branches": refresh.registry.branches,
    "refresh.registry.rebased_branch": refresh.registry.rebased_branch,
    "request.generator_definition.check": requests.generator_definition.check,
    "request.proposed_change.pipeline": requests.proposed_change.pipeline,
    "request.proposed_change.refresh_artifacts": requests.proposed_change.refresh_artifacts,
    "send.echo.request": send.echo.request,
}


async def execute_message(
    routing_key: str, message_body: bytes, service: InfrahubServices, skip_flow: bool = False
) -> MessageTTL | None:
    message_data = ujson.loads(message_body)
    message = messages.MESSAGE_MAP[routing_key](**message_data)
    message.set_log_data(routing_key=routing_key)
    try:
        func = COMMAND_MAP[routing_key]
        if skip_flow and isinstance(func, Flow):
            func = func.fn
        await func(message=message, service=service)
    except Exception as exc:
        if message.reply_requested:
            response = RPCErrorResponse(errors=[str(exc)], initial_message=message.model_dump())
            await service.message_bus.reply_if_initiator_meta(message=response, initiator=message)
            return None
        if message.reached_max_retries:
            service.log.exception("Message failed after maximum number of retries", error=exc)
            await set_check_status(message, conclusion="failure", service=service)
            return None
        message.increase_retry_count()
        await service.message_bus.send(message, delay=MessageTTL.FIVE, is_retry=True)
        return MessageTTL.FIVE
