from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from graphql import graphql
from neo4j import AsyncSession
from starlette.responses import JSONResponse, PlainTextResponse

from infrahub.api.dependencies import get_session
from infrahub.core import get_branch, registry
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp
from infrahub.message_bus.events import (
    InfrahubRPCResponse,
    InfrahubTransformRPC,
    RPCStatusCode,
    TransformMessageAction,
)
from infrahub.message_bus.rpc import InfrahubRpcClient

router = APIRouter()


@router.get("/transform/{transform_url:path}")
async def transform_python(
    request: Request,
    transform_url: str,
    session: AsyncSession = Depends(get_session),
    branch: Optional[str] = None,
    at: Optional[str] = None,
    rebase: Optional[bool] = False,
):
    branch = await get_branch(session=session, branch=branch)

    branch.ephemeral_rebase = rebase
    at = Timestamp(at)

    params = {key: value for key, value in request.query_params.items() if key not in ["branch", "rebase", "at"]}

    transform_schema = registry.schema.get(name="TransformPython", branch=branch)
    transforms = await NodeManager.query(
        session=session, schema=transform_schema, filters={"url__value": transform_url}, branch=branch, at=at
    )

    if not transforms:
        raise HTTPException(status_code=404, detail="Item not found")

    transform = transforms[0]

    query = await transform.query.get_peer(session=session)
    repository = await transform.repository.get_peer(session=session)

    schema = registry.schema.get_schema_branch(name=branch.name)
    gql_schema = await schema.get_graphql_schema(session=session)

    result = await graphql(
        gql_schema,
        source=query.query.value,
        context_value={
            "infrahub_branch": branch,
            "infrahub_at": at,
            "infrahub_database": request.app.state.db,
            "infrahub_session": session,
        },
        root_value=None,
        variable_values=params,
    )

    if result.errors:
        errors = []
        for error in result.errors:
            errors.append(
                {
                    "message": f"GraphQLQuery {query.name.value}: {error.message}",
                    "path": error.path,
                    "locations": [{"line": location.line, "column": location.column} for location in error.locations],
                }
            )

        return JSONResponse(status_code=500, content={"errors": errors})

    rpc_client: InfrahubRpcClient = request.app.state.rpc_client

    response: InfrahubRPCResponse = await rpc_client.call(
        message=InfrahubTransformRPC(
            action=TransformMessageAction.PYTHON,
            repository=repository,
            data=result.data,
            branch_name=branch.name,
            transform_location=f"{transform.file_path.value}::{transform.class_name.value}",
        )
    )

    if response.status == RPCStatusCode.OK.value:
        return response.response["transformed_data"]

    return JSONResponse(status_code=response.status, content={"errors": response.errors})


@router.get("/rfile/{rfile_id}", response_class=PlainTextResponse)
async def generate_rfile(
    request: Request,
    rfile_id: str,
    session: AsyncSession = Depends(get_session),
    branch: Optional[str] = None,
    at: Optional[str] = None,
    rebase: Optional[bool] = False,
):
    branch = await get_branch(session=session, branch=branch)

    branch.ephemeral_rebase = rebase
    at = Timestamp(at)

    params = {key: value for key, value in request.query_params.items() if key not in ["branch", "rebase", "at"]}

    rfile = await NodeManager.get_one(session=session, id=rfile_id, branch=branch, at=at)

    if not rfile:
        rfile_schema = registry.get_schema(name="RFile", branch=branch)
        items = await NodeManager.query(
            session=session, schema=rfile_schema, filters={rfile_schema.default_filter: rfile_id}, branch=branch, at=at
        )
        if items:
            rfile = items[0]

    if not rfile:
        raise HTTPException(status_code=404, detail="Item not found")

    query = await rfile.query.get_peer(session=session)
    repository = await rfile.template_repository.get_peer(session=session)

    schema = registry.schema.get_schema_branch(name=branch.name)
    gql_schema = await schema.get_graphql_schema(session=session)

    result = await graphql(
        gql_schema,
        source=query.query.value,
        context_value={
            "infrahub_branch": branch,
            "infrahub_at": at,
            "infrahub_database": request.app.state.db,
            "infrahub_session": session,
        },
        root_value=None,
        variable_values=params,
    )

    if result.errors:
        errors = []
        for error in result.errors:
            errors.append(
                {
                    "message": f"GraphQLQuery {query.name.value}: {error.message}",
                    "path": error.path,
                    "locations": [{"line": location.line, "column": location.column} for location in error.locations],
                }
            )

        return JSONResponse(status_code=500, content={"errors": errors})

    rpc_client: InfrahubRpcClient = request.app.state.rpc_client

    response: InfrahubRPCResponse = await rpc_client.call(
        message=InfrahubTransformRPC(
            action=TransformMessageAction.JINJA2,
            repository=repository,
            data=result.data,
            branch_name=branch.name,
            transform_location=rfile.template_path.value,
        )
    )

    if response.status == RPCStatusCode.OK.value:
        return response.response["rendered_template"]

    return JSONResponse(status_code=response.status, content={"errors": response.errors})
