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
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import (
    CoreGenericRepository,
    CoreGraphQLQuery,
    CoreTransformJinja2,
    CoreTransformPython,
)
from infrahub.database import InfrahubDatabase  # noqa: TCH001
from infrahub.exceptions import TransformError
from infrahub.graphql import prepare_graphql_params
from infrahub.graphql.utils import extract_data
from infrahub.message_bus.messages import (
    TransformPythonData,
    TransformPythonDataResponse,
)
from infrahub.message_bus.messages.transform_jinja_template import TransformJinjaTemplateData
from infrahub.workflows.catalogue import TRANSFORM_JINJA2_RENDER

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
        kind=CoreTransformPython,
        branch=branch_params.branch,
        at=branch_params.at,
    )

    query = await transform.query.get_peer(db=db, peer_type=CoreGraphQLQuery, raise_on_error=True)
    repository = await transform.repository.get_peer(db=db, peer_type=CoreGenericRepository, raise_on_error=True)

    if repository.commit.value is None:  # type: ignore[attr-defined]
        raise TransformError(
            repository_name=repository.name.value,
            location=repository.location.value,
            commit="n/a",
            message="Repository doesn't have a commit",
        )

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
        repository_id=repository.id,
        repository_name=repository.name.value,
        repository_kind=repository.get_kind(),
        commit=repository.commit.value,  # type: ignore[attr-defined]
        branch=branch_params.branch.name,
        transform_location=f"{transform.file_path.value}::{transform.class_name.value}",
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
        kind=CoreTransformJinja2,
        branch=branch_params.branch,
        at=branch_params.at,
    )

    query = await transform.query.get_peer(db=db, peer_type=CoreGraphQLQuery, raise_on_error=True)
    repository = await transform.repository.get_peer(db=db, peer_type=CoreGenericRepository, raise_on_error=True)

    if repository.commit.value is None:  # type: ignore[attr-defined]
        raise TransformError(
            repository_name=repository.name.value,
            location=repository.location.value,
            commit="n/a",
            message="Repository doesn't have a commit",
        )

    gql_params = prepare_graphql_params(db=request.app.state.db, branch=branch_params.branch, at=branch_params.at)

    result = await graphql(
        schema=gql_params.schema,
        source=query.query.value,
        context_value=gql_params.context,
        root_value=None,
        variable_values=params,
    )

    data = extract_data(query_name=query.name.value, result=result)

    message = TransformJinjaTemplateData(
        repository_id=repository.id,
        repository_name=repository.name.value,
        repository_kind=repository.get_kind(),
        commit=repository.commit.value,  # type: ignore[attr-defined]
        branch=branch_params.branch.name,
        template_location=transform.template_path.value,
        data=data,
    )

    service: InfrahubServices = request.app.state.service

    response: str = await service.workflow.execute(workflow=TRANSFORM_JINJA2_RENDER, message=message)  # type: ignore[arg-type]

    return PlainTextResponse(content=response)
