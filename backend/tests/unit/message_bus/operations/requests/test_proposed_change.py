import os
from typing import Dict, List

from infrahub.message_bus import InfrahubBaseMessage, Meta, messages
from infrahub.message_bus.operations.requests.proposed_change import repository_checks
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from infrahub_client import Config, InfrahubClient
from infrahub_client.playback import JSONPlayback

CURRENT_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
TEST_DATA = f"{CURRENT_DIRECTORY}/test_data"


class BusRecorder(InfrahubMessageBus):
    def __init__(self):
        self.messages: List[InfrahubBaseMessage] = []
        self.messages_per_routing_key: Dict[str, List[InfrahubBaseMessage]] = {}

    async def publish(self, message: InfrahubBaseMessage, routing_key: str) -> None:
        self.messages.append(message)
        if routing_key not in self.messages_per_routing_key:
            self.messages_per_routing_key[routing_key] = []
        self.messages_per_routing_key[routing_key].append(message)

    @property
    def seen_routing_keys(self) -> List[str]:
        return list(self.messages_per_routing_key.keys())


async def test_repository_checks():
    """Validate that a request to trigger respository checks dispatches checks

    Should send one additional message for each branch tied to that repository
    """
    playback = JSONPlayback(directory=f"{TEST_DATA}/repository_checks_01")
    config = Config(address="http://infrahub-testing:8000", requester=playback.async_request)
    client = InfrahubClient(config=config)

    bus_recorder = BusRecorder()
    service = InfrahubServices(client=client, message_bus=bus_recorder)
    message = messages.RequestProposedChangeRepositoryChecks(proposed_change="13a49493-b186-4f7e-a1bb-cd015ed0bdb0")
    await repository_checks(message=message, service=service)
    assert len(bus_recorder.messages) == 2
    assert ["request.repository.checks"] == bus_recorder.seen_routing_keys
    assert (
        messages.RequestRepositoryChecks(
            meta=Meta(request_id=""),
            proposed_change="13a49493-b186-4f7e-a1bb-cd015ed0bdb0",
            repository="b002c0e6-78e6-4a8b-812f-8aa41d89d386",
            branch="test-pc-1",
        )
        in bus_recorder.messages
    )
    assert (
        messages.RequestRepositoryChecks(
            meta=Meta(request_id=""),
            proposed_change="13a49493-b186-4f7e-a1bb-cd015ed0bdb0",
            repository="0af9707a-9c53-450d-96db-d721bfd0350b",
            branch="test-pc-1",
        )
        in bus_recorder.messages
    )
