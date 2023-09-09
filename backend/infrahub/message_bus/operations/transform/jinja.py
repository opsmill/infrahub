from infrahub.git.repository import InfrahubRepository
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubResponse, messages
from infrahub.services import InfrahubServices

log = get_logger()


async def template(message: messages.TransformJinjaTemplate, service: InfrahubServices) -> None:
    log.info(f"Received request to render a Jinja template on branch={message.branch}")

    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name)

    rendered_template = await repo.render_jinja2_template(
        commit=message.commit, location=message.template_location, data={"data": message.data}
    )
    if message.reply_requested:
        response = InfrahubResponse(
            response_class="rendered_template", response_data={"rendered_template": rendered_template}
        )
        await service.reply(message=response, initiator=message)
