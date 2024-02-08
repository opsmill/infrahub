from infrahub_sdk import UUIDT, InfrahubClient

from infrahub.core.constants import InfrahubKind
from infrahub.git import InfrahubRepository
from infrahub.message_bus import Meta, messages
from infrahub.services import InfrahubServices


async def test_transform_python_success(git_fixture_repo: InfrahubRepository, helper):
    commit = git_fixture_repo.get_commit_value(branch_name="main")

    correlation_id = str(UUIDT())
    message = messages.TransformPythonData(
        repository_id=str(git_fixture_repo.id),
        repository_name=git_fixture_repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=commit,
        branch="main",
        transform_location="unit/transforms/multiplier.py::Multiplier",
        data={"multiplier": 2, "key": "abc", "answer": 21},
        meta=Meta(reply_to="ci-testing", correlation_id=correlation_id),
    )

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(message_bus=bus_simulator, client=InfrahubClient())
    bus_simulator.service = service

    await service.send(message=message)
    assert len(bus_simulator.replies) == 1
    reply: messages.TransformPythonDataResponse = bus_simulator.replies[0]
    assert reply.passed
    assert reply.meta.correlation_id == correlation_id
    assert reply.response_data.transformed_data == {"key": "abcabc", "answer": 42}
