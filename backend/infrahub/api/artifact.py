from typing import TYPE_CHECKING, Dict, Optional

from fastapi import APIRouter, Depends, Request, Response
from neo4j import AsyncSession
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

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


class ArtifactGenerateResult(BaseModel):
    changed: Optional[bool] = None
    checksum: Optional[str] = None
    object_id: Optional[str] = None
    artifact_id: Optional[str] = None
    status_code: int


class ArtifactGenerateResponse(BaseModel):
    nodes: Dict[str, ArtifactGenerateResult] = Field(default_factory=dict)


@router.get("/{artifact_id:str}")
async def get_artifact(
    artifact_id: str,
    session: AsyncSession = Depends(get_session),
    branch_params: BranchParams = Depends(get_branch_params),
    _: str = Depends(get_current_user),
) -> Response:
    artifact = await registry.manager.get_one(
        session=session, id=artifact_id, branch=branch_params.branch, at=branch_params.at
    )
    if not artifact:
        raise NodeNotFound(
            branch_name=config.SETTINGS.main.default_branch, node_type="CoreArtifact", identifier=artifact_id
        )

    content = await registry.storage.retrieve(identifier=artifact.object_id.value)

    return Response(content=content, headers={"Content-Type": artifact.content_type.value})


@router.get("/generate/{artifact_definition_id:str}")
async def generate_artifact(
    request: Request,
    artifact_definition_id: str,
    session: AsyncSession = Depends(get_session),
    branch_params: BranchParams = Depends(get_branch_params),
    _: str = Depends(get_current_user),
) -> ArtifactGenerateResponse:
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

    response_data = ArtifactGenerateResponse()

    for member_id, member in members.items():
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
        if not isinstance(response.response, dict):
            return JSONResponse(status_code=500, content={"errors": ["No content received from InfrahubArtifactRPC."]})

        response_data.nodes[member_id] = ArtifactGenerateResult(status_code=response.status, **response.response)

    return response_data
