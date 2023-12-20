import os

from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.playback import JSONPlayback

from infrahub.message_bus import Meta, messages
from infrahub.message_bus.operations.requests.proposed_change import repository_checks
from infrahub.services import InfrahubServices

CURRENT_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
TEST_DATA = f"{CURRENT_DIRECTORY}/test_data"


async def test_repository_checks(helper):
    """Validate that a request to trigger respository checks dispatches checks

    Should send one additional message for each branch tied to that repository
    """
    playback = JSONPlayback(directory=f"{TEST_DATA}/repository_checks_01")
    config = Config(address="http://infrahub-testing:8000", requester=playback.async_request)
    client = InfrahubClient(config=config)
    proposed_change_id = "1790fa8f-dd4d-ed00-58dd-18835e51189a"
    repository1_id = "1790fa5c-68b5-c478-58da-18835608efda"
    repository2_id = "1790fa6d-1654-9068-58df-1883e684d3fd"

    bus_recorder = helper.get_message_bus_recorder()
    service = InfrahubServices(client=client, message_bus=bus_recorder)
    message = messages.RequestProposedChangeRepositoryChecks(proposed_change=proposed_change_id)
    await repository_checks(message=message, service=service)
    assert len(bus_recorder.messages) == 4
    assert ["request.repository.checks", "request.repository.user_checks"] == bus_recorder.seen_routing_keys
    assert (
        messages.RequestRepositoryChecks(
            meta=Meta(request_id=""),
            proposed_change=proposed_change_id,
            repository=repository1_id,
            source_branch="test-pc-1",
            target_branch="main",
        )
        in bus_recorder.messages
    )
    assert (
        messages.RequestRepositoryChecks(
            meta=Meta(request_id=""),
            proposed_change=proposed_change_id,
            repository=repository2_id,
            source_branch="test-pc-1",
            target_branch="main",
        )
        in bus_recorder.messages
    )
    assert messages.RequestRepositoryUserChecks(
        meta=Meta(request_id=""),
        proposed_change="1790fa8f-dd4d-ed00-58dd-18835e51189a",
        repository="1790fa6d-1654-9068-58df-1883e684d3fd",
        source_branch="test-pc-1",
        target_branch="main",
    )
