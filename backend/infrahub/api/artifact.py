from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request, Response
from pydantic import BaseModel, Field

from infrahub.api.dependencies import BranchParams, get_branch_params, get_current_user, get_db
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.protocols import CoreArtifactDefinition
from infrahub.database import InfrahubDatabase  # noqa: TCH001
from infrahub.exceptions import NodeNotFoundError
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.log import get_logger
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE

log = get_logger()
router = APIRouter(prefix="/artifact")


class ArtifactGeneratePayload(BaseModel):
    nodes: list[str] = Field(default_factory=list)


class ArtifactGenerateResponse(BaseModel):
    nodes: list[str]


@router.get("/{artifact_id:str}")
async def get_artifact(
    artifact_id: str,
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    _: str = Depends(get_current_user),
) -> Response:
    artifact = await registry.manager.get_one(db=db, id=artifact_id, branch=branch_params.branch, at=branch_params.at)
    if not artifact:
        raise NodeNotFoundError(
            branch_name=branch_params.branch.name, node_type=InfrahubKind.ARTIFACT, identifier=artifact_id
        )

    return Response(
        content=registry.storage.retrieve(identifier=artifact.storage_id.value),
        headers={"Content-Type": artifact.content_type.value.value},
    )


@router.post("/generate/{artifact_definition_id:str}")
async def generate_artifact(
    request: Request,
    artifact_definition_id: str,
    payload: ArtifactGeneratePayload = Body(
        ArtifactGeneratePayload(),
        description="Payload of the request, can be used to limit the scope of the query to a specific list of hosts",
    ),
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    _: str = Depends(get_current_user),
) -> None:
    # Verify that the artifact definition exists for the requested branch
    artifact_definition = await registry.manager.get_one_by_id_or_default_filter(
        db=db,
        id=artifact_definition_id,
        kind=CoreArtifactDefinition,
        branch=branch_params.branch,
    )

    service = request.app.state.service
    model = RequestArtifactDefinitionGenerate(
        artifact_definition=artifact_definition.id, branch=branch_params.branch.name, limit=payload.nodes
    )

    await service.workflow.submit_workflow(workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE, parameters={"model": model})
