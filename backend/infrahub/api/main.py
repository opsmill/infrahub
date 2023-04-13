import logging
import os
import time
from typing import Optional

import graphene
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.logger import logger
from fastapi.responses import JSONResponse
from graphql import graphql
from neo4j import AsyncSession
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.responses import PlainTextResponse
from starlette_exporter import PrometheusMiddleware, handle_metrics

import infrahub.config as config
from infrahub.api import diff, internal, schema, transformation
from infrahub.api.dependencies import get_session
from infrahub.auth import BaseTokenAuth
from infrahub.core import get_branch, registry
from infrahub.core.initialization import initialization
from infrahub.core.manager import NodeManager
from infrahub.database import get_db
from infrahub.exceptions import BranchNotFound
from infrahub.graphql import get_gql_mutation, get_gql_query
from infrahub.graphql.app import InfrahubGraphQLApp
from infrahub.message_bus import close_broker_connection, connect_to_broker
from infrahub.message_bus.rpc import InfrahubRpcClient
from infrahub.middleware import InfrahubCORSMiddleware
from infrahub_client.timestamp import Timestamp

app = FastAPI(
    title="Infrahub",
    version="0.2.0",
    contact={
        "name": "OpsMill",
        "email": "info@opsmill.com",
    },
)

# pylint: disable=too-many-locals

gunicorn_logger = logging.getLogger("gunicorn.error")
logger.handlers = gunicorn_logger.handlers


app.include_router(schema.router)
app.include_router(transformation.router)
app.include_router(internal.router)
app.include_router(diff.router)


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


@app.exception_handler(BranchNotFound)
async def api_exception_handler(_: Request, exc: BranchNotFound) -> JSONResponse:
    """Generic API Exception handler."""
    error_code, error = exc.api_response()
    return JSONResponse(status_code=error_code, content=error)


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
    branch = await get_branch(session=session, branch=branch)

    branch.ephemeral_rebase = rebase
    at = Timestamp(at)

    params = {key: value for key, value in request.query_params.items() if key not in ["branch", "rebase", "at"]}

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
app.add_middleware(InfrahubCORSMiddleware)

app.add_route(path="/metrics", route=handle_metrics)
app.add_route(path="/graphql", route=InfrahubGraphQLApp(playground=True), methods=["GET", "POST", "OPTIONS"])
app.add_route(
    path="/graphql/{branch_name:str}", route=InfrahubGraphQLApp(playground=True), methods=["GET", "POST", "OPTIONS"]
)
app.add_websocket_route(path="/graphql", route=InfrahubGraphQLApp())
app.add_websocket_route(path="/graphql/{branch_name:str}", route=InfrahubGraphQLApp())

if __name__ != "main":
    logger.setLevel(gunicorn_logger.level)
