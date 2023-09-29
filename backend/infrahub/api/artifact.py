from __future__ import annotations

from typing import TYPE_CHECKING, List, Dict

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from infrahub import config
from infrahub.api.dependencies import (
    BranchParams,
    get_branch_params,
    get_current_user,
    get_db,
)
from infrahub.core import registry
from infrahub.database import InfrahubDatabase  # noqa: TCH001
from infrahub.exceptions import NodeNotFound
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.artifact import CoreArtifactDefinition
    from infrahub.message_bus.rpc import InfrahubRpcClient

log = get_logger()
router = APIRouter(prefix="/artifact")


class ArtifactGeneratePayload(BaseModel):
    nodes: List[str] = Field(default_factory=list)


class ArtifactGenerateResponse(BaseModel):
    nodes: List[Dict[str, str]]


@router.get("/{artifact_id:str}")
async def get_artifact(
    artifact_id: str,
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    _: str = Depends(get_current_user),
) -> Response:
    artifact = await registry.manager.get_one(db=db, id=artifact_id, branch=branch_params.branch, at=branch_params.at)
    if not artifact:
        raise NodeNotFound(
            branch_name=config.SETTINGS.main.default_branch, node_type="CoreArtifact", identifier=artifact_id
        )

    content = await registry.storage.retrieve(identifier=artifact.storage_id.value)

    return Response(content=content, headers={"Content-Type": artifact.content_type.value})


@router.post("/generate/{artifact_definition_id:str}")
async def generate_artifact(
    request: Request,
    artifact_definition_id: str,
    payload: ArtifactGeneratePayload = ArtifactGeneratePayload(),
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    _: str = Depends(get_current_user),
) -> ArtifactGenerateResponse:
    artifact_definition: CoreArtifactDefinition = await registry.manager.get_one_by_id_or_default_filter(
        db=db,
        id=artifact_definition_id,
        schema_name="CoreArtifactDefinition",
        branch=branch_params.branch,
        at=branch_params.at,
    )

    rpc_client: InfrahubRpcClient = request.app.state.rpc_client

    nodes = await artifact_definition.generate(db=db, rpc_client=rpc_client, nodes=payload.nodes)

    response_data = ArtifactGenerateResponse(nodes=nodes)

    return response_data
