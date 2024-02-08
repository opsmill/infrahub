from infrahub_sdk import UUIDT

from infrahub.core.constants import InfrahubKind
from infrahub.git import InfrahubRepository
from infrahub.message_bus import Meta, RPCErrorResponse, messages
from infrahub.services import InfrahubServices


async def test_git_transform_jinja2_success(git_repo_jinja: InfrahubRepository, helper):
    commit = git_repo_jinja.get_commit_value(branch_name="main")
    correlation_id = str(UUIDT())
    message = messages.TransformJinjaTemplate(
        repository_id=str(UUIDT()),
        repository_name=git_repo_jinja.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=commit,
        branch="main",
        template_location="template01.tpl.j2",
        data={"data": {"items": ["consilium", "potum", "album", "magnum"]}},
        meta=Meta(reply_to="ci-testing", correlation_id=correlation_id),
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

    await service.send(message=message)
    assert len(bus_simulator.replies) == 1
    reply: messages.TransformJinjaTemplateResponse = bus_simulator.replies[0]
    assert reply.passed
    assert reply.meta.correlation_id == correlation_id
    assert reply.data.rendered_template == expected_response


async def test_git_transform_jinja2_missing(git_repo_jinja: InfrahubRepository, helper):
    commit = git_repo_jinja.get_commit_value(branch_name="main")
    correlation_id = str(UUIDT())
    message = messages.TransformJinjaTemplate(
        repository_id=str(UUIDT()),
        repository_name=git_repo_jinja.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=commit,
        branch="main",
        template_location="template03.tpl.j2",
        data={"data": {"items": ["consilium", "potum", "album", "magnum"]}},
        meta=Meta(reply_to="ci-testing", correlation_id=correlation_id),
    )

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(message_bus=bus_simulator)
    bus_simulator.service = service

    await service.send(message=message)
    assert len(bus_simulator.replies) == 1
    reply: RPCErrorResponse = bus_simulator.replies[0]
    assert not reply.passed
    assert reply.meta.correlation_id == correlation_id
    assert "Unable to find the file" in reply.data.error


async def test_git_transform_jinja2_invalid(git_repo_jinja: InfrahubRepository, helper):
    commit = git_repo_jinja.get_commit_value(branch_name="main")
    correlation_id = str(UUIDT())
    message = messages.TransformJinjaTemplate(
        repository_id=str(UUIDT()),
        repository_name=git_repo_jinja.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=commit,
        branch="main",
        template_location="template02.tpl.j2",
        data={"data": {"items": ["consilium", "potum", "album", "magnum"]}},
        meta=Meta(reply_to="ci-testing", correlation_id=correlation_id),
    )

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(message_bus=bus_simulator)
    bus_simulator.service = service

    await service.send(message=message)
    assert len(bus_simulator.replies) == 1
    reply: RPCErrorResponse = bus_simulator.replies[0]
    assert not reply.passed
    assert reply.meta.correlation_id == correlation_id
    assert reply.routing_key == "rpc_error"
    assert "Encountered unknown tag 'end'." in reply.data.error
