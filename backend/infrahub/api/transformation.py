from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Path, Request
from graphql import graphql
from starlette.responses import JSONResponse, PlainTextResponse

from infrahub.api.dependencies import (
    BranchParams,
    get_branch_params,
    get_current_user,
    get_db,
)
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase  # noqa: TCH001
from infrahub.graphql import prepare_graphql_params
from infrahub.graphql.utils import extract_data
from infrahub.message_bus.messages import (
    TransformJinjaTemplate,
    TransformJinjaTemplateResponse,
    TransformPythonData,
    TransformPythonDataResponse,
)

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices

router = APIRouter()


@router.get("/transform/python/{transform_id:str}")
async def transform_python(
    request: Request,
    transform_id: str,
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    _: str = Depends(get_current_user),
) -> JSONResponse:
    params = {key: value for key, value in request.query_params.items() if key not in ["branch", "at"]}

    transform = await NodeManager.get_one_by_id_or_default_filter(
        db=db,
        id=transform_id,
        schema_name=InfrahubKind.TRANSFORMPYTHON,
        branch=branch_params.branch,
        at=branch_params.at,
    )

    query = await transform.query.get_peer(db=db)  # type: ignore[attr-defined]
    repository = await transform.repository.get_peer(db=db)  # type: ignore[attr-defined]

    gql_params = prepare_graphql_params(db=request.app.state.db, branch=branch_params.branch, at=branch_params.at)

    result = await graphql(
        schema=gql_params.schema,
        source=query.query.value,
        context_value=gql_params.context,
        root_value=None,
        variable_values=params,
    )

    data = extract_data(query_name=query.name.value, result=result)

    service: InfrahubServices = request.app.state.service

    message = TransformPythonData(
        repository_id=repository.id,  # type: ignore[attr-defined]
        repository_name=repository.name.value,  # type: ignore[attr-defined]
        repository_kind=repository.get_kind(),
        commit=repository.commit.value,  # type: ignore[attr-defined]
        branch=branch_params.branch.name,
        transform_location=f"{transform.file_path.value}::{transform.class_name.value}",  # type: ignore[attr-defined]
        data=data,
    )

    response = await service.message_bus.rpc(message=message, response_class=TransformPythonDataResponse)
    return JSONResponse(content=response.data.transformed_data)


@router.get("/transform/jinja2/{transform_id}", response_class=PlainTextResponse)
async def transform_jinja2(
    request: Request,
    transform_id: str = Path(description="ID or Name of the Jinja2 Transform to render"),
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    _: str = Depends(get_current_user),
) -> PlainTextResponse:
    params = {key: value for key, value in request.query_params.items() if key not in ["branch", "at"]}

    transform = await NodeManager.get_one_by_id_or_default_filter(
        db=db,
        id=transform_id,
        schema_name=InfrahubKind.TRANSFORMJINJA2,
        branch=branch_params.branch,
        at=branch_params.at,
    )

    query = await transform.query.get_peer(db=db)  # type: ignore[attr-defined]
    repository = await transform.repository.get_peer(db=db)  # type: ignore[attr-defined]

    gql_params = prepare_graphql_params(db=request.app.state.db, branch=branch_params.branch, at=branch_params.at)

    result = await graphql(
        schema=gql_params.schema,
        source=query.query.value,
        context_value=gql_params.context,
        root_value=None,
        variable_values=params,
    )

    data = extract_data(query_name=query.name.value, result=result)

    service: InfrahubServices = request.app.state.service

    message = TransformJinjaTemplate(
        repository_id=repository.id,  # type: ignore[attr-defined]
        repository_name=repository.name.value,  # type: ignore[attr-defined]
        repository_kind=repository.get_kind(),
        commit=repository.commit.value,  # type: ignore[attr-defined]
        branch=branch_params.branch.name,
        template_location=transform.template_path.value,  # type: ignore[attr-defined]
        data=data,
    )

    response = await service.message_bus.rpc(message=message, response_class=TransformJinjaTemplateResponse)
    return PlainTextResponse(content=response.data.rendered_template)
