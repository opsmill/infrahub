from infrahub_sdk import InfrahubClient

from infrahub.core.constants import InfrahubKind
from infrahub.git import InfrahubRepository
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices


async def test_transform_python_success(git_fixture_repo: InfrahubRepository, helper):
    commit = git_fixture_repo.get_commit_value(branch_name="main")

    message = messages.TransformPythonData(
        repository_id=str(git_fixture_repo.id),
        repository_name=git_fixture_repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=commit,
        branch="main",
        transform_location="unit/transforms/multiplier.py::Multiplier",
        data={"multiplier": 2, "key": "abc", "answer": 21},
    )

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(message_bus=bus_simulator, client=InfrahubClient())
    bus_simulator.service = service

    reply = await service.message_bus.rpc(message=message, response_class=messages.TransformPythonDataResponse)
    assert reply.passed
    assert reply.data.transformed_data == {"key": "abcabc", "answer": 42}
