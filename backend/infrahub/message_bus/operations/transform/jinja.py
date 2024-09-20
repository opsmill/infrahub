from prefect import flow

from infrahub.git.repository import get_initialized_repo
from infrahub.log import get_logger
from infrahub.message_bus.messages.transform_jinja_template import (
    TransformJinjaTemplate,
    TransformJinjaTemplateData,
    TransformJinjaTemplateResponse,
    TransformJinjaTemplateResponseData,
)
from infrahub.services import InfrahubServices, services

log = get_logger()


async def template(message: TransformJinjaTemplate, service: InfrahubServices) -> None:
    log.info(f"Received request to render a Jinja template on branch={message.branch}")

    repo = await get_initialized_repo(
        repository_id=message.repository_id,
        name=message.repository_name,
        service=service,
        repository_kind=message.repository_kind,
    )

    rendered_template = await repo.render_jinja2_template(
        commit=message.commit, location=message.template_location, data={"data": message.data}
    )
    if message.reply_requested:
        response = TransformJinjaTemplateResponse(
            data=TransformJinjaTemplateResponseData(rendered_template=rendered_template),
        )
        await service.reply(message=response, initiator=message)


@flow(persist_result=True)
async def transform_render_jinja2_template(message: TransformJinjaTemplateData) -> str:
    service = services.service
    repo = await get_initialized_repo(
        repository_id=message.repository_id,
        name=message.repository_name,
        service=service,
        repository_kind=message.repository_kind,
    )

    rendered_template = await repo.render_jinja2_template(
        commit=message.commit, location=message.template_location, data={"data": message.data}
    )

    return rendered_template
