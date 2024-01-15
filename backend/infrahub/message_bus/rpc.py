from __future__ import annotations

from typing import TYPE_CHECKING, List

from infrahub.services import services

if TYPE_CHECKING:
    from . import InfrahubMessage


class InfrahubRpcClientBase:
    async def send(self, message: InfrahubMessage) -> None:
        await services.send(message=message)


class InfrahubRpcClient(InfrahubRpcClientBase):
    pass


class InfrahubRpcClientTesting(InfrahubRpcClientBase):
    """InfrahubRPCClient instrumented for testing and mocking."""

    def __init__(self) -> None:
        self.sent: List[InfrahubMessage] = []

    async def send(self, message: InfrahubMessage) -> None:
        self.sent.append(message)
