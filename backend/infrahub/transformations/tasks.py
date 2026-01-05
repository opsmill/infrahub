from typing import Any

from prefect import flow

from infrahub.git.repository import get_initialized_repo
from infrahub.log import get_logger
from infrahub.workers.dependencies import get_client
from infrahub.workflows.utils import add_branch_tag

from .models import TransformJinjaTemplateData, TransformPythonData

log = get_logger()


@flow(name="transform_render_python", flow_run_name="Render transform python", persist_result=True)
async def transform_python(message: TransformPythonData) -> Any:
    await add_branch_tag(branch_name=message.branch)

    client = get_client()

    repo = await get_initialized_repo(
        client=client,
        repository_id=message.repository_id,
        name=message.repository_name,
        repository_kind=message.repository_kind,
        commit=message.commit,
    )

    transformed_data = await repo.execute_python_transform.with_options(timeout_seconds=message.timeout)(
        client=client,
        branch_name=message.branch,
        commit=message.commit,
        location=message.transform_location,
        data=message.data,
        convert_query_response=message.convert_query_response,
    )  # type: ignore[misc]

    return transformed_data


@flow(name="transform_render_jinja2_template", flow_run_name="Render transform Jinja2", persist_result=True)
async def transform_render_jinja2_template(message: TransformJinjaTemplateData) -> str:
    await add_branch_tag(branch_name=message.branch)

    client = get_client()

    repo = await get_initialized_repo(
        client=client,
        repository_id=message.repository_id,
        name=message.repository_name,
        repository_kind=message.repository_kind,
        commit=message.commit,
    )

    rendered_template = await repo.render_jinja2_template.with_options(timeout_seconds=message.timeout)(
        commit=message.commit, location=message.template_location, data={"data": message.data}
    )  # type: ignore[misc]

    return rendered_template
