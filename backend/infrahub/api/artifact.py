from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Body, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from infrahub.api.dependencies import (
    BranchParams,
    get_branch_params,
    get_context,
    get_current_user,
    get_db,
    get_permission_manager,
)
from infrahub.artifacts.content import get_artifact_content_reader
from infrahub.branch.status_checker import BranchStatusChecker
from infrahub.core import registry
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import GLOBAL_BRANCH_NAME, ArtifactEncryption, InfrahubKind, PermissionAction
from infrahub.core.merge.write_blocker import MergeWriteBlocker
from infrahub.core.protocols import CoreArtifact, CoreArtifactDefinition
from infrahub.database import InfrahubDatabase  # noqa: TC001
from infrahub.exceptions import BranchStatusError, NodeNotFoundError, ValidationError
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.log import get_logger
from infrahub.permissions.constants import PermissionDecisionFlag
from infrahub.storage_encryption.status import EncryptionCheck, UnreadableReason
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession
    from infrahub.context import InfrahubContext
    from infrahub.permissions import PermissionManager
    from infrahub.services import InfrahubServices

log = get_logger()
router = APIRouter(prefix="/artifact")


class ArtifactGeneratePayload(BaseModel):
    nodes: list[str] = Field(default_factory=list)


class ArtifactGenerateResponse(BaseModel):
    nodes: list[str]


class ArtifactEncryptionCheckResponse(BaseModel):
    encryption: ArtifactEncryption = Field(
        description="Encryption of the stored file of the artifact, as found by this check"
    )
    reason: UnreadableReason | None = Field(
        default=None, description="Why the file cannot be read with the current key, when it cannot"
    )
    updated: bool = Field(description="Whether this check changed the encryption value stored on the artifact")


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

    content = await get_artifact_content_reader(db=db).read_artifact(
        storage_id=str(artifact.storage_id.value), checksum=artifact.checksum.value
    )
    return Response(content=content, headers={"Content-Type": artifact.content_type.value.value})


@router.post("/{artifact_id:str}/encryption")
async def check_artifact_encryption(
    request: Request,
    artifact_id: str,
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    permission_manager: PermissionManager = Depends(get_permission_manager),
    context: InfrahubContext = Depends(get_context),
    _: AccountSession = Depends(get_current_user),
) -> ArtifactEncryptionCheckResponse:
    """Check from its header whether the stored file of an artifact is encrypted and readable with the current key.

    The check does not decrypt the file, so a file modified after it was stored still reports as encrypted until it
    is read. When the result differs from the encryption value stored on the artifact, the value is updated if the
    caller may update artifacts and the branch accepts writes; otherwise the result is returned as it is.

    Raises:
        NodeNotFoundError: If the artifact does not exist on the branch.

    """
    artifact = await registry.manager.get_one(
        db=db, id=artifact_id, branch=branch_params.branch, at=branch_params.at, kind=CoreArtifact
    )
    if not artifact:
        raise NodeNotFoundError(
            branch_name=branch_params.branch.name, node_type=InfrahubKind.ARTIFACT, identifier=artifact_id
        )

    stored = (
        ArtifactEncryption(artifact.encryption.value.value)
        if artifact.encryption.value
        else ArtifactEncryption.PLAINTEXT
    )
    storage_id = artifact.storage_id.value
    if storage_id:
        check: EncryptionCheck = await run_in_threadpool(registry.storage.inspect_encryption, str(storage_id))
    else:
        check = EncryptionCheck(encryption=None, reason=UnreadableReason.MISSING)

    # A missing file says nothing about its encryption, so the stored value stays.
    found = check.encryption or stored
    updated = False
    if found != stored and await _may_store_encryption(
        request=request, db=db, branch_params=branch_params, permission_manager=permission_manager
    ):
        artifact.get_attribute("encryption").value = found.value
        await artifact.save(db=db, user_id=context.account.account_id)
        updated = True

    return ArtifactEncryptionCheckResponse(encryption=found, reason=check.reason, updated=updated)


async def _may_store_encryption(
    request: Request, db: InfrahubDatabase, branch_params: BranchParams, permission_manager: PermissionManager
) -> bool:
    permission_decision = (
        PermissionDecisionFlag.ALLOW_DEFAULT
        if branch_params.branch.name in (GLOBAL_BRANCH_NAME, registry.default_branch)
        else PermissionDecisionFlag.ALLOW_OTHER
    )
    permission = ObjectPermission(
        namespace="Core",
        name="Artifact",
        action=PermissionAction.UPDATE.value,
        decision=permission_decision,
    )
    if not permission_manager.has_permission(permission=permission):
        return False
    try:
        await BranchStatusChecker(
            db=db, merge_write_blocker=MergeWriteBlocker(cache=request.app.state.service.cache)
        ).check(branch=branch_params.branch)
    except BranchStatusError:
        return False
    return True


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
        if branch_params.branch.name in (GLOBAL_BRANCH_NAME, registry.default_branch)
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
