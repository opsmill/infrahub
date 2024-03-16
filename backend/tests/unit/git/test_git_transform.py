from infrahub_sdk import UUIDT

from infrahub.core.constants import InfrahubKind
from infrahub.git import InfrahubRepository
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices


async def test_git_transform_jinja2_success(git_repo_jinja: InfrahubRepository, helper):
    commit = git_repo_jinja.get_commit_value(branch_name="main")
    message = messages.TransformJinjaTemplate(
        repository_id=str(UUIDT()),
        repository_name=git_repo_jinja.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=commit,
        branch="main",
        template_location="template01.tpl.j2",
        data={"items": ["consilium", "potum", "album", "magnum"]},
    )
    expected_response = """
consilium
potum
album
magnum
"""

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(message_bus=bus_simulator)
    bus_simulator.service = service

    reply = await service.message_bus.rpc(message=message, response_class=messages.TransformJinjaTemplateResponse)
    assert reply.passed
    assert reply.data.rendered_template == expected_response


async def test_git_transform_jinja2_missing(git_repo_jinja: InfrahubRepository, helper):
    commit = git_repo_jinja.get_commit_value(branch_name="main")

    message = messages.TransformJinjaTemplate(
        repository_id=str(UUIDT()),
        repository_name=git_repo_jinja.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=commit,
        branch="main",
        template_location="template03.tpl.j2",
        data={"data": {"items": ["consilium", "potum", "album", "magnum"]}},
    )

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(message_bus=bus_simulator)
    bus_simulator.service = service

    reply = await service.message_bus.rpc(message=message, response_class=messages.TransformJinjaTemplateResponse)
    assert not reply.passed
    assert "Unable to find the file" in reply.errors[0]


async def test_git_transform_jinja2_invalid(git_repo_jinja: InfrahubRepository, helper, caplog):
    commit = git_repo_jinja.get_commit_value(branch_name="main")

    message = messages.TransformJinjaTemplate(
        repository_id=str(UUIDT()),
        repository_name=git_repo_jinja.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=commit,
        branch="main",
        template_location="template02.tpl.j2",
        data={"data": {"items": ["consilium", "potum", "album", "magnum"]}},
    )

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(message_bus=bus_simulator)
    bus_simulator.service = service

    reply = await service.message_bus.rpc(message=message, response_class=messages.TransformJinjaTemplateResponse)
    assert not reply.passed
    assert "Encountered unknown tag 'end'." in reply.errors[0]
