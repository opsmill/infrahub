import logging
import os
import time
from typing import Optional

import graphene
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.logger import logger
from graphql import graphql
from neo4j import AsyncSession
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.responses import JSONResponse, PlainTextResponse
from starlette_exporter import PrometheusMiddleware, handle_metrics

import infrahub.config as config
from infrahub.auth import BaseTokenAuth
from infrahub.core import get_branch, registry
from infrahub.core.initialization import initialization
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp
from infrahub.database import get_db
from infrahub.graphql import get_gql_mutation, get_gql_query
from infrahub.graphql.app import InfrahubGraphQLApp
from infrahub.message_bus import close_broker_connection, connect_to_broker
from infrahub.message_bus.events import (
    InfrahubRPCResponse,
    InfrahubTransformRPC,
    RPCStatusCode,
    TransformMessageAction,
)
from infrahub.message_bus.rpc import InfrahubRpcClient

app = FastAPI()

# pylint: disable=too-many-locals

gunicorn_logger = logging.getLogger("gunicorn.error")
logger.handlers = gunicorn_logger.handlers


async def get_session(request: Request) -> AsyncSession:
    session = request.app.state.db.session(database=config.SETTINGS.database.database)
    try:
        yield session
    finally:
        await session.close()


@app.on_event("startup")
async def app_initialization():

    if not config.SETTINGS:
        config_file_name = os.environ.get("INFRAHUB_CONFIG", "infrahub.toml")
        config_file_path = os.path.abspath(config_file_name)
        logger.info(f"Loading the configuration from {config_file_path}")
        config.load_and_exit(config_file_path)

    # Initialize database Driver and load local registry
    app.state.db = await get_db()

    async with app.state.db.session(database=config.SETTINGS.database.database) as session:
        await initialization(session=session)

    # Initialize connection to the RabbitMQ bus
    await connect_to_broker()

    # Initialize RPC Client
    app.state.rpc_client = await InfrahubRpcClient().connect()


@app.on_event("shutdown")
async def shutdown():
    await close_broker_connection()
    await app.state.db.close()


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.get("/rfile/{rfile_id}", response_class=PlainTextResponse)
async def generate_rfile(
    request: Request,
    rfile_id: str,
    session: AsyncSession = Depends(get_session),
    branch: Optional[str] = None,
    at: Optional[str] = None,
    rebase: Optional[bool] = False,
):

    params = {key: value for key, value in request.query_params.items() if key not in ["branch", "rebase", "at"]}

    branch = await get_branch(session=session, branch=branch)
    branch.ephemeral_rebase = rebase
    at = Timestamp(at)

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

    result = await graphql(
        graphene.Schema(
            query=await get_gql_query(session=session, branch=branch),
            mutation=await get_gql_mutation(session=session, branch=branch),
            auto_camelcase=False,
        ).graphql_schema,
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


@app.get("/query/{query_id}")
async def graphql_query(
    request: Request,
    response: Response,
    query_id: str,
    session: AsyncSession = Depends(get_session),
    branch: Optional[str] = None,
    at: Optional[str] = None,
    rebase: bool = False,
):

    params = {key: value for key, value in request.query_params.items() if key not in ["branch", "rebase", "at"]}

    branch = await get_branch(session=session, branch=branch)
    branch.ephemeral_rebase = rebase
    at = Timestamp(at)

    gql_query = await NodeManager.get_one(session=session, id=query_id, branch=branch, at=at)

    if not gql_query:
        gqlquery_schema = registry.get_schema(name="GraphQLQuery", branch=branch)
        items = await NodeManager.query(
            session=session,
            schema=gqlquery_schema,
            filters={gqlquery_schema.default_filter: query_id},
            branch=branch,
            at=at,
        )
        if items:
            gql_query = items[0]

    if not gql_query:
        raise HTTPException(status_code=404, detail="Item not found")

    result = await graphql(
        graphene.Schema(
            query=await get_gql_query(session=session, branch=branch),
            mutation=await get_gql_mutation(session=session, branch=branch),
            auto_camelcase=False,
        ).graphql_schema,
        source=gql_query.query.value,
        context_value={
            "infrahub_branch": branch,
            "infrahub_at": at,
            "infrahub_database": request.app.state.db,
            "infrahub_session": session,
        },
        root_value=None,
        variable_values=params,
    )

    response_payload = {"data": result.data}

    if result.errors:
        response_payload["errors"] = []
        for error in result.errors:
            response_payload["errors"].append(
                {
                    "message": error.message,
                    "path": error.path,
                    "locations": [{"line": location.line, "column": location.column} for location in error.locations],
                }
            )
        response.status_code = 500

    return response_payload


@app.get("/transform/{transform_url:path}")
async def transform_python(
    request: Request,
    transform_url: str,
    session: AsyncSession = Depends(get_session),
    branch: Optional[str] = None,
    at: Optional[str] = None,
    rebase: Optional[bool] = False,
):

    params = {key: value for key, value in request.query_params.items() if key not in ["branch", "rebase", "at"]}

    branch = await get_branch(session=session, branch=branch)
    branch.ephemeral_rebase = rebase
    at = Timestamp(at)

    transform_schema = registry.get_schema(name="TransformPython", branch=branch)
    transforms = await NodeManager.query(
        session=session, schema=transform_schema, filters={"url__value": transform_url}, branch=branch, at=at
    )

    if not transforms:
        raise HTTPException(status_code=404, detail="Item not found")

    transform = transforms[0]

    query = await transform.query.get_peer(session=session)
    repository = await transform.repository.get_peer(session=session)

    result = await graphql(
        graphene.Schema(
            query=await get_gql_query(session=session, branch=branch),
            mutation=await get_gql_mutation(session=session, branch=branch),
            auto_camelcase=False,
        ).graphql_schema,
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


app.add_middleware(
    AuthenticationMiddleware,
    backend=BaseTokenAuth(),
    on_error=lambda _, exc: PlainTextResponse(str(exc), status_code=401),
)

app.add_middleware(
    PrometheusMiddleware,
    app_name="infrahub",
    group_paths=True,
    prefix="infrahub",
    buckets=[0.1, 0.25, 0.5],
    skip_paths=["/health"],
)
app.add_route("/metrics", handle_metrics)

app.add_route("/graphql", InfrahubGraphQLApp())
app.add_route("/graphql/{branch_name:str}", InfrahubGraphQLApp())
app.add_websocket_route("/graphql", InfrahubGraphQLApp())
app.add_websocket_route("/graphql/{branch_name:str}", InfrahubGraphQLApp())

if __name__ != "main":
    logger.setLevel(gunicorn_logger.level)
