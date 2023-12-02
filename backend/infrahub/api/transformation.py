from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from graphql import graphql
from starlette.responses import JSONResponse, PlainTextResponse

from infrahub.api.dependencies import (
    BranchParams,
    get_branch_params,
    get_current_user,
    get_db,
)
from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase  # noqa: TCH001
from infrahub.message_bus import messages
from infrahub.message_bus.responses import TemplateResponse, TransformResponse

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices

router = APIRouter()


@router.get("/transform/{transform_url:path}")
async def transform_python(
    request: Request,
    transform_url: str,
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    _: str = Depends(get_current_user),
) -> JSONResponse:
    params = {key: value for key, value in request.query_params.items() if key not in ["branch", "rebase", "at"]}

    transform_schema = registry.get_node_schema(name="CoreTransformPython", branch=branch_params.branch)
    transforms = await NodeManager.query(
        db=db,
        schema=transform_schema,
        filters={"url__value": transform_url},
        branch=branch_params.branch,
        at=branch_params.at,
    )

    if not transforms:
        raise HTTPException(status_code=404, detail="Item not found")

    transform = transforms[0]

    query = await transform.query.get_peer(db=db)  # type: ignore[attr-defined]
    repository = await transform.repository.get_peer(db=db)  # type: ignore[attr-defined]

    schema = registry.schema.get_schema_branch(name=branch_params.branch.name)
    gql_schema = await schema.get_graphql_schema(db=db)

    result = await graphql(
        gql_schema,
        source=query.query.value,
        context_value={
            "infrahub_branch": branch_params.branch,
            "infrahub_at": branch_params.at,
            "infrahub_database": request.app.state.db,
        },
        root_value=None,
        variable_values=params,
    )

    if result.errors:
        errors = []
        for error in result.errors:
            error_locations = error.locations or []
            errors.append(
                {
                    "message": f"GraphQLQuery {query.name.value}: {error.message}",
                    "path": error.path,
                    "locations": [{"line": location.line, "column": location.column} for location in error_locations],
                }
            )

        return JSONResponse(status_code=500, content={"errors": errors})

    service: InfrahubServices = request.app.state.service

    message = messages.TransformPythonData(
        repository_id=repository.id,  # type: ignore[attr-defined]
        repository_name=repository.name.value,  # type: ignore[attr-defined]
        commit=repository.commit.value,  # type: ignore[attr-defined]
        branch=branch_params.branch.name,
        transform_location=f"{transform.file_path.value}::{transform.class_name.value}",  # type: ignore[attr-defined]
        data=result.data,
    )

    response = await service.message_bus.rpc(message=message)
    template = response.parse(response_class=TransformResponse)

    return JSONResponse(content=template.transformed_data)


@router.get("/rfile/{rfile_id}", response_class=PlainTextResponse)
async def generate_rfile(
    request: Request,
    rfile_id: str = Path(description="ID or Name of the RFile to render"),
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    _: str = Depends(get_current_user),
) -> PlainTextResponse:
    params = {key: value for key, value in request.query_params.items() if key not in ["branch", "rebase", "at"]}

    rfile = await NodeManager.get_one_by_id_or_default_filter(
        db=db, id=rfile_id, schema_name="CoreRFile", branch=branch_params.branch, at=branch_params.at
    )

    query = await rfile.query.get_peer(db=db)  # type: ignore[attr-defined]
    repository = await rfile.repository.get_peer(db=db)  # type: ignore[attr-defined]

    schema = registry.schema.get_schema_branch(name=branch_params.branch.name)
    gql_schema = await schema.get_graphql_schema(db=db)

    result = await graphql(
        gql_schema,
        source=query.query.value,
        context_value={
            "infrahub_branch": branch_params.branch,
            "infrahub_at": branch_params.at,
            "infrahub_database": request.app.state.db,
        },
        root_value=None,
        variable_values=params,
    )

    if result.errors:
        errors = []
        for error in result.errors:
            error_locations = error.locations or []
            errors.append(
                {
                    "message": f"GraphQLQuery {query.name.value}: {error.message}",
                    "path": error.path,
                    "locations": [{"line": location.line, "column": location.column} for location in error_locations],
                }
            )

        return JSONResponse(status_code=500, content={"errors": errors})

    service: InfrahubServices = request.app.state.service

    message = messages.TransformJinjaTemplate(
        repository_id=repository.id,  # type: ignore[attr-defined]
        repository_name=repository.name.value,  # type: ignore[attr-defined]
        commit=repository.commit.value,  # type: ignore[attr-defined]
        branch=branch_params.branch.name,
        template_location=rfile.template_path.value,  # type: ignore[attr-defined]
        data=result.data,
    )

    response = await service.message_bus.rpc(message=message)
    template = response.parse(response_class=TemplateResponse)

    return PlainTextResponse(content=template.rendered_template)
