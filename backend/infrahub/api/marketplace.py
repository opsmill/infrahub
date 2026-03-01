from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request

from infrahub.api.dependencies import get_current_user
from infrahub.exceptions import HTTPServerError
from infrahub.log import get_logger
from infrahub.marketplace.client import MarketplaceClient
from infrahub.marketplace.models import (
    MarketplaceCollectionsListResponse,
    MarketplaceInstallModel,
    MarketplaceInstallRequest,
    MarketplaceSchemasListResponse,
    MarketplaceTagCount,
    MarketplaceVersionContent,
)
from infrahub.workflows.catalogue import MARKETPLACE_SCHEMA_INSTALL

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.services import InfrahubServices

log = get_logger()
router = APIRouter(prefix="/marketplace")


@router.get("/schemas")
async def get_schemas(
    request: Request,
    search: str | None = Query(None, description="Case-insensitive search on name or display_name"),
    tags: str | None = Query(None, description="Comma-separated tag names to filter by"),
    _: AccountSession = Depends(get_current_user),
) -> MarketplaceSchemasListResponse:
    """Fetch available schemas from the marketplace, with optional filtering."""
    service: InfrahubServices = request.app.state.service
    client = MarketplaceClient(http=service.http)

    try:
        result = await client.get_schemas()
    except HTTPServerError:
        raise

    schemas = list(result.schemas)

    if search:
        search_lower = search.lower()
        schemas = [s for s in schemas if search_lower in s.name.lower() or search_lower in s.display_name.lower()]

    if tags:
        tag_names = {t.strip().lower() for t in tags.split(",") if t.strip()}
        schemas = [s for s in schemas if any(tag.name.lower() in tag_names for tag in s.tags)]

    return MarketplaceSchemasListResponse(schemas=schemas, total_count=len(schemas))


@router.get("/collections")
async def get_collections(
    request: Request,
    _: AccountSession = Depends(get_current_user),
) -> MarketplaceCollectionsListResponse:
    """Fetch available collections from the marketplace."""
    service: InfrahubServices = request.app.state.service
    client = MarketplaceClient(http=service.http)

    try:
        return await client.get_collections()
    except HTTPServerError:
        raise


@router.get("/tags")
async def get_tags(
    request: Request,
    _: AccountSession = Depends(get_current_user),
) -> list[MarketplaceTagCount]:
    """Fetch available tags with counts from the marketplace."""
    service: InfrahubServices = request.app.state.service
    client = MarketplaceClient(http=service.http)

    try:
        return await client.get_tags()
    except HTTPServerError:
        raise


@router.get("/schemas/{schema_id}/versions/{version_id}")
async def get_schema_version_content(
    request: Request,
    schema_id: str,  # noqa: ARG001
    version_id: str,
    _: AccountSession = Depends(get_current_user),
) -> MarketplaceVersionContent:
    """Fetch the full content of a specific schema version."""
    service: InfrahubServices = request.app.state.service
    client = MarketplaceClient(http=service.http)

    try:
        return await client.get_schema_version_content(version_id=version_id)
    except HTTPServerError:
        raise


@router.post("/install", status_code=202)
async def install_schemas(
    request: Request,
    body: MarketplaceInstallRequest,
    _: AccountSession = Depends(get_current_user),
) -> dict[str, str]:
    """Trigger background installation of marketplace schemas into a repository."""
    service: InfrahubServices = request.app.state.service

    model = MarketplaceInstallModel(
        repository_id=body.repository_id,
        schema_ids=body.schema_ids,
        collection_ids=body.collection_ids,
        branch_name=body.branch_name,
    )

    workflow_info = await service.workflow.submit_workflow(
        workflow=MARKETPLACE_SCHEMA_INSTALL,
        parameters={"model": model},
    )

    return {"task_id": str(workflow_info.id), "message": "Schema installation started"}
