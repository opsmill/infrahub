from infrahub.message_bus import InfrahubBaseMessage


class InfrahubMessageBus:
    async def publish(self, message: InfrahubBaseMessage, routing_key: str) -> None:
        raise NotImplementedError()

    async def reply(self, message: InfrahubBaseMessage, routing_key: str) -> None:
        raise NotImplementedError()
