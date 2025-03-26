from prefect import flow

from infrahub.message_bus import messages
from infrahub.message_bus.messages.send_echo_request import SendEchoRequestResponse, SendEchoRequestResponseData
from infrahub.services import InfrahubServices


@flow(name="echo-request")
async def request(message: messages.SendEchoRequest, service: InfrahubServices) -> None:
    service.log.info(f"Received message: {message.message}")
    if message.reply_requested:
        response = SendEchoRequestResponse(data=SendEchoRequestResponseData(response=f"Reply to: {message.message}"))
        await service.message_bus.reply_if_initiator_meta(message=response, initiator=message)
