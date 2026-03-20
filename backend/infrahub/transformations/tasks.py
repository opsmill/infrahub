from typing import Any

from prefect import flow

from infrahub.git.repository import get_initialized_repo
from infrahub.log import get_logger
from infrahub.workers.dependencies import get_client
from infrahub.workflows.utils import add_branch_tag

from .models import TransformAIData, TransformJinjaTemplateData, TransformPythonData

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
    )  # type: ignore[call-overload]

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
    )  # type: ignore[call-overload]

    return rendered_template


def _build_attribute_descriptions(schema: Any) -> list[dict[str, Any]]:
    """Build a list of attribute descriptions for non-read-only attributes."""
    descriptions = []
    for attr in schema.attributes:
        if attr.read_only:
            continue
        desc: dict[str, Any] = {
            "name": attr.name,
            "kind": attr.kind,
            "optional": attr.optional,
        }
        if attr.description:
            desc["description"] = attr.description
        if attr.enum:
            desc["enum"] = attr.enum
        if attr.choices:
            desc["choices"] = attr.choices
        if attr.max_length:
            desc["max_length"] = attr.max_length
        if attr.regex:
            desc["regex"] = attr.regex
        descriptions.append(desc)
    return descriptions


@flow(name="transform_render_ai", flow_run_name="Render transform AI", persist_result=True)
async def transform_ai(message: TransformAIData) -> dict[str, Any]:
    await add_branch_tag(branch_name=message.branch)

    client = get_client()

    repo = await get_initialized_repo(
        client=client,
        repository_id=message.repository_id,
        name=message.repository_name,
        repository_kind=message.repository_kind,
        commit=message.commit,
    )

    report_data = await repo.execute_ai_transform.with_options(timeout_seconds=message.timeout)(
        client=client,
        branch_name=message.branch,
        commit=message.commit,
        prompt_template_path=message.prompt_template_path,
        data=message.data,
        model=message.model,
        temperature=message.temperature,
        max_tokens=message.max_tokens,
        output_format=message.output_format,
        mcp_server_url=message.mcp_server_url,
    )  # type: ignore[call-overload]

    if message.result_kind:
        from infrahub.transformations.ai_client import AIClient

        ext = "csv" if message.output_format == "csv" else "md"
        transform_name = report_data.get("template", "ai-report").replace("/", "_").removesuffix(".md.j2")
        filename = f"{transform_name}.{ext}"

        schema = await client.schema.get(kind=message.result_kind, branch=message.branch)
        attr_descriptions = _build_attribute_descriptions(schema)

        attr_values: dict[str, Any] = {}
        if attr_descriptions:
            ai_client = AIClient(
                model=message.model,
                temperature=message.temperature,
                max_tokens=message.max_tokens,
            )
            attr_values = await ai_client.generate_attribute_values(
                attributes=attr_descriptions,
                context={
                    "transform_name": transform_name,
                    "report_content": report_data["content"],
                    "data": message.data,
                    "output_format": message.output_format,
                },
            )
            # Remove null values so they don't override schema defaults
            attr_values = {k: v for k, v in attr_values.items() if v is not None}

        result_node = await client.create(kind=message.result_kind, branch=message.branch, **attr_values)
        result_node.upload_from_bytes(content=report_data["content"].encode("utf-8"), name=filename)
        await result_node.save()

        report_data["result_id"] = result_node.id
        log.info(f"Stored AI transform result as {message.result_kind} with id {result_node.id}")

    return report_data
