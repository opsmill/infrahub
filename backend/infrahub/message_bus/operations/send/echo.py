from prefect import flow

from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.send_echo_request import SendEchoRequestResponse, SendEchoRequestResponseData
from infrahub.workers.dependencies import get_message_bus


@flow(name="echo-request")
async def request(message: messages.SendEchoRequest) -> None:
    get_logger().info(f"Received message: {message.message}")

    if message.reply_requested:
        response = SendEchoRequestResponse(data=SendEchoRequestResponseData(response=f"Reply to: {message.message}"))
        message_bus = await get_message_bus()
        await message_bus.reply_if_initiator_meta(message=response, initiator=message)
