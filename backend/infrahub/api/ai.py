from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from infrahub import config
from infrahub.api.dependencies import (
    BranchParams,
    get_branch_params,
    get_context,
    get_current_user,
    get_db,
    get_permission_manager,
)
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, PermissionAction
from infrahub.core.protocols import CoreFileObject
from infrahub.database import InfrahubDatabase  # noqa: TC001
from infrahub.exceptions import NodeNotFoundError
from infrahub.permissions import define_object_permission_from_branch
from infrahub.workflows.catalogue import FILE_OBJECT_AI_EXTRACTION

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.context import InfrahubContext
    from infrahub.permissions import PermissionManager
    from infrahub.services import InfrahubServices

router = APIRouter(prefix="/ai")


class ExtractionResponse(BaseModel):
    ok: bool
    message: str


@router.post(
    "/extract/{node_id}",
    response_model=ExtractionResponse,
    summary="Trigger AI data extraction for a file object",
    description=(
        "Submits a background workflow that uses the Claude API to extract structured data "
        "from the file attached to the given CoreFileObject node and writes the extracted "
        "values back to the node's attributes. Requires UPDATE permission on the node."
    ),
)
async def trigger_ai_extraction(
    node_id: str,
    request: Request,
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    permission_manager: PermissionManager = Depends(get_permission_manager),
    context: InfrahubContext = Depends(get_context),
    _: AccountSession = Depends(get_current_user),
) -> ExtractionResponse:
    if not config.SETTINGS.ai.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="AI extraction is not configured. Set INFRAHUB_AI_ANTHROPIC_API_KEY to enable this feature.",
        )

    # Fetch the node (validates it exists and inherits CoreFileObject)
    try:
        node = await registry.manager.get_one(
            db=db,
            id=node_id,
            kind=CoreFileObject,
            branch=branch_params.branch,
            at=branch_params.at,
            raise_on_error=True,
        )
    except NodeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if InfrahubKind.FILEOBJECT not in node.get_schema().inherit_from:
        raise HTTPException(
            status_code=422,
            detail=f"Node {node_id} does not inherit from CoreFileObject.",
        )

    # Check UPDATE permission
    permission = define_object_permission_from_branch(
        schema=node.get_schema(), action=PermissionAction.UPDATE, branch_name=branch_params.branch.name
    )
    permission_manager.raise_for_permission(permission=permission)

    service: InfrahubServices = request.app.state.service
    await service.workflow.submit_workflow(
        workflow=FILE_OBJECT_AI_EXTRACTION,
        context=context,
        parameters={
            "branch_name": branch_params.branch.name,
            "node_id": node.id,
            "node_kind": node.get_kind(),
            "context": context,
        },
    )

    return ExtractionResponse(ok=True, message=f"AI extraction queued for node {node_id}.")
