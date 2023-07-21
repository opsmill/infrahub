from typing import TYPE_CHECKING, Dict

from fastapi import APIRouter, Depends, Request, Response
from neo4j import AsyncSession
from starlette.responses import JSONResponse, PlainTextResponse

from infrahub import config
from infrahub.api.dependencies import (
    BranchParams,
    get_branch_params,
    get_current_user,
    get_session,
)
from infrahub.core import registry
from infrahub.exceptions import NodeNotFound
from infrahub.log import get_logger
from infrahub.message_bus.events import (
    ArtifactMessageAction,
    InfrahubArtifactRPC,
    InfrahubRPCResponse,
)

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.message_bus.rpc import InfrahubRpcClient
log = get_logger()
router = APIRouter(prefix="/artifact")


@router.get("")
@router.get("/{artifact_id:str}")
async def get_artifact(
    artifact_id: str,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(get_current_user),
) -> Response:
    artifact = await registry.manager.get_one(session=session, id=artifact_id)
    if not artifact:
        raise NodeNotFound(
            branch_name=config.SETTINGS.main.default_branch, node_type="CoreArtifact", identifier=artifact_id
        )

    content = registry.storage.retrieve(identifier=artifact_id)

    if artifact.content_type.value == "application/json":
        return JSONResponse(content=content)

    if artifact.content_type.value == "text/plain":
        return PlainTextResponse(content=content)

    return Response(content=content)


@router.get("/generate/{artifact_definition_id:str}")
async def generate_artifact(
    request: Request,
    artifact_definition_id: str,
    session: AsyncSession = Depends(get_session),
    branch_params: BranchParams = Depends(get_branch_params),
    _: str = Depends(get_current_user),
) -> Response:
    artifact_definition = await registry.manager.get_one(
        session=session, id=artifact_definition_id, branch=branch_params.branch, at=branch_params.at
    )
    if not artifact_definition:
        raise NodeNotFound(
            branch_name=config.SETTINGS.main.default_branch,
            node_type="CoreArtifactDefinition",
            identifier=artifact_definition_id,
        )

    group: Node = await artifact_definition.targets.get_peer(session=session)  # type: ignore[attr-defined]
    transformation: Node = await artifact_definition.transformation.get_peer(session=session)  # type: ignore[attr-defined]
    members: Dict[str, Node] = await group.members.get_peers(session=session)  # type: ignore[attr-defined]

    query: Node = await transformation.query.get_peer(session=session)  # type: ignore[attr-defined]
    repository: Node = await transformation.repository.get_peer(session=session)  # type: ignore[attr-defined]

    rpc_client: InfrahubRpcClient = request.app.state.rpc_client

    # def extract_parameters(obj, parameters):

    #     result = {}
    #     for key, value in parameters.items():
    #         att_name, prop_name = value.split("__")
    #         attr = getattr(obj, att_name)
    #         result[key] = getattr(attr, prop_name)

    #     return result

    # Find the Group
    #  For each member of the group
    #   Extract the parameters
    #   Generate the Artifacts

    response_data = {}

    for member_id, member in members.items():
        # parameters = extract_parameters(  obj=member, parameters=artifact_definition.parameters.value)

        # TODO execute in parallel
        message = InfrahubArtifactRPC(
            action=ArtifactMessageAction.GENERATE,
            repository=repository,
            target=await member.to_graphql(session=session),
            definition=await artifact_definition.to_graphql(session=session),
            branch_name=branch_params.branch.name,
            query=await query.to_graphql(session=session),
            transformation=await transformation.to_graphql(session=session),
        )

        response: InfrahubRPCResponse = await rpc_client.call(message=message)
        response_data[member_id] = {"status_code": response.status}

        # if not isinstance(response.response, dict):
        #     return JSONResponse(status_code=500, content={"errors": ["No content received from InfrahubTransformRPC."]})

        # if response.status == RPCStatusCode.OK.value:
        #     return JSONResponse(content=response.response.get("transformed_data"))

    return JSONResponse(status_code=200, content={"nodes": response_data})
