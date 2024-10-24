from typing import Any

from prefect import flow

from infrahub.git.repository import get_initialized_repo
from infrahub.log import get_logger
from infrahub.services import services
from infrahub.workflows.utils import add_branch_tag

from .models import TransformJinjaTemplateData, TransformPythonData

log = get_logger()


@flow(name="transform-render-python")
async def transform_python(message: TransformPythonData) -> Any:
    service = services.service
    await add_branch_tag(branch_name=message.branch)

    repo = await get_initialized_repo(
        repository_id=message.repository_id,
        name=message.repository_name,
        service=service,
        repository_kind=message.repository_kind,
    )

    transformed_data = await repo.execute_python_transform(
        branch_name=message.branch,
        commit=message.commit,
        location=message.transform_location,
        data=message.data,
        client=service.client,
    )

    return transformed_data


@flow(name="transform-render-jinja2")
async def transform_render_jinja2_template(message: TransformJinjaTemplateData) -> str:
    service = services.service
    await add_branch_tag(branch_name=message.branch)

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
