from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Body, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError

from infrahub import config
from infrahub.api.dependencies import (
    BranchParams,
    get_branch_params,
    get_context,
    get_current_user,
    get_db,
    get_permission_manager,
)
from infrahub.artifacts.content import ArtifactContentReader
from infrahub.artifacts.render_result import (
    RENDER_RESULT_RUNNING,
    RenderProgressResponse,
    RenderResultAcceptor,
    RenderResultPayload,
    check_render_id,
)
from infrahub.artifacts.render_token import mint_render_token, validate_render_token
from infrahub.branch.status_checker import BranchStatusChecker
from infrahub.core import registry
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind, PermissionAction
from infrahub.core.merge.write_blocker import MergeWriteBlocker
from infrahub.core.protocols import CoreArtifact, CoreArtifactDefinition
from infrahub.database import InfrahubDatabase  # noqa: TC001
from infrahub.exceptions import (
    AuthorizationError,
    BranchStatusError,
    NodeNotFoundError,
    RenderResultInvalidError,
    ValidationError,
)
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.log import get_logger
from infrahub.permissions.constants import PermissionDecisionFlag
from infrahub.webhook.constants import RENDER_TOKEN_HEADER
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession
    from infrahub.context import InfrahubContext
    from infrahub.permissions import PermissionManager
    from infrahub.services import InfrahubServices

log = get_logger()
router = APIRouter(prefix="/artifact")

BYTES_PER_MEGABYTE = 1024 * 1024

render_token_scheme = APIKeyHeader(name=RENDER_TOKEN_HEADER, auto_error=False)


class ArtifactGeneratePayload(BaseModel):
    nodes: list[str] = Field(default_factory=list)


class ArtifactGenerateResponse(BaseModel):
    nodes: list[str]


@router.get("/{artifact_id:str}")
async def get_artifact(
    artifact_id: str,
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    _: AccountSession = Depends(get_current_user),
) -> Response:
    artifact = await registry.manager.get_one(
        db=db, id=artifact_id, branch=branch_params.branch, at=branch_params.at, kind=CoreArtifact
    )
    if not artifact:
        raise NodeNotFoundError(
            branch_name=branch_params.branch.name, node_type=InfrahubKind.ARTIFACT, identifier=artifact_id
        )

    content = await ArtifactContentReader(
        db=db, storage=registry.storage, verify_checksum=config.SETTINGS.storage.verify_artifact_checksum
    ).read_artifact(storage_id=str(artifact.storage_id.value), checksum=artifact.checksum.value)
    return Response(content=content, headers={"Content-Type": artifact.content_type.value.value})


@router.post("/generate/{artifact_definition_id:str}")
async def generate_artifact(
    request: Request,
    artifact_definition_id: str,
    payload: ArtifactGeneratePayload = Body(
        ArtifactGeneratePayload(),  # noqa: B008
        description="Payload of the request, can be used to limit the scope of the query to a specific list of hosts",
    ),
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    permission_manager: PermissionManager = Depends(get_permission_manager),
    context: InfrahubContext = Depends(get_context),
) -> None:
    try:
        await BranchStatusChecker(
            db=db, merge_write_blocker=MergeWriteBlocker(cache=request.app.state.service.cache)
        ).check(branch=branch_params.branch)
    except BranchStatusError as err:
        raise ValidationError(input_value=str(err)) from err

    permission_decision = (
        PermissionDecisionFlag.ALLOW_DEFAULT
        if branch_params.branch.name in {GLOBAL_BRANCH_NAME, registry.default_branch}
        else PermissionDecisionFlag.ALLOW_OTHER
    )
    permissions = [
        ObjectPermission(namespace="Core", name="Artifact", action=action.value, decision=permission_decision)
        for action in (PermissionAction.CREATE, PermissionAction.UPDATE)
    ]
    permission_manager.raise_for_permissions(permissions=permissions)

    # Verify that the artifact definition exists for the requested branch
    artifact_definition = await registry.manager.get_one_by_id_or_default_filter(
        db=db,
        id=artifact_definition_id,
        kind=CoreArtifactDefinition,
        branch=branch_params.branch,
    )

    service: InfrahubServices = request.app.state.service
    model = RequestArtifactDefinitionGenerate(
        artifact_definition_id=artifact_definition.id,
        artifact_definition_name=artifact_definition.name.value,
        branch=branch_params.branch.name,
        limit=payload.nodes,
    )

    # No explicit priority: the fan-out inherits the catalogue default (MEDIUM), like the
    # same generation triggered through the artifact-definition mutation. Dispatching at
    # HIGH would stamp the whole task tree -- including every per-target /api/query call
    # the workers make -- as X-Priority: high, making a user-triggered regeneration of
    # thousands of artifacts unsheddable by the admission layer at the same class as
    # interactive traffic.
    await service.workflow.submit_workflow(
        workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE,
        context=context,
        parameters={"model": model},
    )


@router.post(
    "/render/{render_id:str}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_200_OK: {
            "model": RenderProgressResponse,
            "description": "Progress accepted: the deadline moved and a new token is returned",
        }
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": RenderResultPayload.model_json_schema()}},
        }
    },
)
async def submit_render_result(
    request: Request,
    render_id: str,
    render_token: str | None = Depends(render_token_scheme),
    db: InfrahubDatabase = Depends(get_db),
) -> Response:
    """Accept the content, the failure or a progress report an external engine returns for a render request.

    Only the render token authenticates this request, so account sessions and API keys are refused.

    Raises:
        AuthorizationError: When the render token is missing or not valid.
        RenderResultInvalidError: When the body is not a valid render result.

    """
    if not render_token:
        raise AuthorizationError(f"A render token is required in the {RENDER_TOKEN_HEADER} header")
    claims = validate_render_token(token=render_token)
    check_render_id(render_id=render_id, claims=claims)

    # The body is parsed here, after the token checks, so that a request without a valid token gets 401, not 400.
    try:
        body = RenderResultPayload.model_validate_json(await request.body())
    except PydanticValidationError as exc:
        raise RenderResultInvalidError(
            "; ".join(
                f"{'.'.join(str(loc) for loc in error['loc']) or 'body'}: {error['msg']}" for error in exc.errors()
            )
        ) from None

    service: InfrahubServices = request.app.state.service
    acceptor = RenderResultAcceptor(
        db=db,
        storage=registry.storage,
        event_service=service.event,
        max_content_bytes=config.SETTINGS.storage.max_file_size * BYTES_PER_MEGABYTE,
    )
    if body.status == RENDER_RESULT_RUNNING:
        deadline = await acceptor.report_progress(render_id=render_id, claims=claims, message=body.message)
        progress = RenderProgressResponse(
            render_id=render_id,
            deadline=deadline,
            token=mint_render_token(
                render_id=render_id, artifact_id=claims.artifact_id, branch=claims.branch, deadline=deadline
            ),
        )
        return JSONResponse(status_code=status.HTTP_200_OK, content=progress.model_dump(mode="json"))

    await acceptor.accept_render_result(render_id=render_id, claims=claims, body=body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
