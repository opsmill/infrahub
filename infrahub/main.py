import os
import time
import logging
from typing import Optional

import graphene
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.logger import logger
from graphql import graphql
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.responses import PlainTextResponse, JSONResponse
from starlette_exporter import PrometheusMiddleware, handle_metrics

from neo4j import AsyncSession

import infrahub.config as config
from infrahub.auth import BaseTokenAuth
from infrahub.message_bus import connect_to_broker, close_broker_connection
from infrahub.message_bus.rpc import InfrahubRpcClient
from infrahub.message_bus.events import InfrahubTransformRPC, TransformMessageAction, InfrahubRPCResponse, RPCStatusCode

from infrahub.core import get_branch, registry
from infrahub.database import get_db
from infrahub.core.initialization import initialization
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp
from infrahub.graphql import get_gql_mutation, get_gql_query
from infrahub.graphql.app import InfrahubGraphQLApp


app = FastAPI()

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
        rfile_schema = await registry.get_schema(session=session, name="RFile")
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

    graphql_query = await NodeManager.get_one(session=session, id=query_id, branch=branch, at=at)

    if not graphql_query:
        gqlquery_schema = await registry.get_schema(session=session, name="GraphQLQuery")
        items = await NodeManager.query(
            session=session,
            schema=gqlquery_schema,
            filters={gqlquery_schema.default_filter: query_id},
            branch=branch,
            at=at,
        )
        if items:
            graphql_query = items[0]

    if not graphql_query:
        raise HTTPException(status_code=404, detail="Item not found")

    result = await graphql(
        graphene.Schema(
            query=await get_gql_query(session=session, branch=branch),
            mutation=await get_gql_mutation(session=session, branch=branch),
            auto_camelcase=False,
        ).graphql_schema,
        source=graphql_query.query.value,
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


# -------------------------------------------------------------------
# OpenConfig Experiment
# -------------------------------------------------------------------

QUERY_INTERFACES = """
query($device: String!) {
    device(name__value: $device) {
        id
        interfaces {
            name {
                value
            }
            description {
                value
            }
            enabled {
                value
            }
            ip_addresses {
                address {
                    value
                }
            }
        }
    }
}
"""


@app.get("/openconfig/interfaces")
async def openconfig_interfaces(
    request: Request,
    response: Response,
    device: str,
    branch: Optional[str] = None,
    at: Optional[str] = None,
    rebase: Optional[bool] = False,
):
    params = {key: value for key, value in request.query_params.items() if key not in ["branch", "rebase", "at"]}

    branch = await get_branch(branch)
    branch.ephemeral_rebase = rebase
    at = Timestamp(at)

    result = await graphql(
        graphene.Schema(
            query=get_gql_query(branch=branch), mutation=get_gql_mutation(branch=branch), auto_camelcase=False
        ).graphql_schema,
        source=QUERY_INTERFACES,
        context_value={
            "infrahub_branch": branch,
            "infrahub_at": at,
        },
        root_value=None,
        variable_values=params,
    )

    response_payload = {}

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

    response_payload["openconfig-interfaces:interface"] = []

    for intf in result.data.get("device")[0].get("interfaces"):

        intf_name = intf["name"]["value"]

        intf_config = {
            "name": intf_name,
            "config": {"enabled": intf["enabled"]["value"]},
        }

        if intf["description"] and intf["description"]["value"]:
            intf_config["config"]["description"] = intf["description"]["value"]

        if intf["ip_addresses"]:
            intf_config["subinterfaces"] = {"subinterface": []}

        for idx, ip in enumerate(intf["ip_addresses"]):

            address, mask = ip["address"]["value"].split("/")
            intf_config["subinterfaces"]["subinterface"].append(
                {
                    "index": idx,
                    "openconfig-if-ip:ipv4": {
                        "addresses": {"address": [{"ip": address, "config": {"ip": address, "prefix-length": mask}}]},
                        "config": {"enabled": True},
                    },
                }
            )

        response_payload["openconfig-interfaces:interface"].append(intf_config)

    return response_payload


QUERY_BGP_NEIGHBORS = """
query($device: String!) {
  bgp_session(device__name__value: $device) {
    id
    peer_group {
      name {
        value
      }
    }
    local_ip {
      address {
        value
      }
    }
    remote_ip {
      address {
        value
      }
    }
    local_as {
      asn {
        value
      }
    }
    remote_as {
      asn {
        value
      }
    }
    description {
      value
    }
  }
}
"""


@app.get("/openconfig/network-instances/network-instance/protocols/protocol/bgp/neighbors")
async def openconfig_bgp(
    request: Request,
    response: Response,
    device: str,
    branch: Optional[str] = None,
    at: Optional[str] = None,
    rebase: Optional[bool] = False,
):
    params = {key: value for key, value in request.query_params.items() if key not in ["branch", "rebase", "at"]}

    branch = await get_branch(branch)
    branch.ephemeral_rebase = rebase
    at = Timestamp(at)

    result = await graphql(
        graphene.Schema(
            query=get_gql_query(branch=branch), mutation=get_gql_mutation(branch=branch), auto_camelcase=False
        ).graphql_schema,
        source=QUERY_BGP_NEIGHBORS,
        context_value={
            "infrahub_branch": branch,
            "infrahub_at": at,
        },
        root_value=None,
        variable_values=params,
    )

    response_payload = {}

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

    response_payload["openconfig-bgp:neighbors"] = {"neighbor": []}

    for session in result.data.get("bgp_session"):

        neighbor_address = session["remote_ip"]["address"]["value"].split("/")[0]
        session_data = {"neighbor-address": neighbor_address, "config": {"neighbor-address": neighbor_address}}

        if session["peer_group"]:
            session_data["config"]["peer-group"] = session["peer_group"]["name"]["value"]

        if session["remote_as"]:
            session_data["config"]["peer-as"] = session["remote_as"]["asn"]["value"]

        if session["local_as"]:
            session_data["config"]["local-as"] = session["local_as"]["asn"]["value"]

        response_payload["openconfig-bgp:neighbors"]["neighbor"].append(session_data)

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
app.add_route("/metrics", handle_metrics)

app.add_route("/graphql", InfrahubGraphQLApp())
app.add_route("/graphql/{branch_name:str}", InfrahubGraphQLApp())
app.add_websocket_route("/graphql", InfrahubGraphQLApp())
app.add_websocket_route("/graphql/{branch_name:str}", InfrahubGraphQLApp())

if __name__ != "main":
    logger.setLevel(gunicorn_logger.level)
