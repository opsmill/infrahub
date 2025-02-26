from pydantic import Field

from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "send.echo.request"


class SendEchoRequest(InfrahubMessage):
    """Sent a echo request, a ping message for example."""

    message: str = Field(..., description="The message to send")


class SendEchoRequestResponseData(InfrahubResponseData):
    response: str = Field(default="", description="The response string")


class SendEchoRequestResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: SendEchoRequestResponseData
