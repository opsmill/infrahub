from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from infrahub.message_bus.events import InfrahubRPC, InfrahubRPCResponse, RPCStatusCode

if TYPE_CHECKING:
    from infrahub_client import InfrahubClient

LOGGER = logging.getLogger("infrahub.git")


async def handle_bad_request(  # pylint: disable=unused-argument
    message: InfrahubRPC, client: InfrahubClient
) -> InfrahubRPCResponse:
    return InfrahubRPCResponse(status=RPCStatusCode.BAD_REQUEST)


async def handle_not_found(  # pylint: disable=unused-argument
    message: InfrahubRPC, client: InfrahubClient
) -> InfrahubRPCResponse:
    return InfrahubRPCResponse(status=RPCStatusCode.NOT_FOUND)


async def handle_not_implemented(  # pylint: disable=unused-argument
    message: InfrahubRPC, client: InfrahubClient
) -> InfrahubRPCResponse:
    return InfrahubRPCResponse(status=RPCStatusCode.NOT_IMPLEMENTED)


async def handle_message(message: InfrahubRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    return await handle_not_found(message=message, client=client)
