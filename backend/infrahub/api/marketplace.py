"""REST proxy endpoints for `marketplace.infrahub.app`.

Frontend never calls the Marketplace directly (CORS constraint); all traffic
flows through this proxy. Endpoints require authentication via `get_current_user`.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.api.dependencies import get_current_user
from infrahub.core.constants import InfrahubKind
from infrahub.log import get_logger
from infrahub.marketplace.cli_snippet import parse_install_item, render_cli_snippet
from infrahub.marketplace.client import (
    MarketplaceClient,
    MarketplaceMisconfiguredError,
    MarketplaceNotFoundError,
    MarketplaceTimeoutError,
    MarketplaceUnreachableError,
    make_marketplace_client,
)
from infrahub.marketplace.models import (
    CliSnippetResponse,
    MarketplaceCollectionDetail,
    MarketplaceCollectionsListResponse,
    MarketplaceInstallDirectPayload,
    MarketplaceInstallItem,
    MarketplaceInstallPayload,
    MarketplaceInstallRequest,
    MarketplaceInstallResponse,
    MarketplaceSchemaDetail,
    MarketplaceSchemasListResponse,
    MarketplaceStatus,
    MarketplaceTagsResponse,
    MarketplaceVersionContent,
)
from infrahub.workers.dependencies import get_client, get_workflow
from infrahub.workflows.catalogue import MARKETPLACE_SCHEMA_INSTALL, MARKETPLACE_SCHEMA_INSTALL_DIRECT

if TYPE_CHECKING:
    from infrahub.auth import AccountSession

log = get_logger()

router = APIRouter(prefix="/marketplace", tags=["marketplace"])

# Short-TTL in-memory caches keyed by query params.
_CACHE_TTL_SECONDS = 30.0
_cache_schemas_list: dict[tuple, tuple[float, MarketplaceSchemasListResponse]] = {}
_cache_collections_list: dict[tuple, tuple[float, MarketplaceCollectionsListResponse]] = {}
_cache_tags: tuple[float, MarketplaceTagsResponse] | None = None


# --- Helpers ---


def _map_upstream_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MarketplaceMisconfiguredError):
        return HTTPException(status_code=500, detail="marketplace_misconfigured")
    if isinstance(exc, MarketplaceNotFoundError):
        return HTTPException(status_code=404, detail="not_found")
    if isinstance(exc, MarketplaceTimeoutError):
        return HTTPException(status_code=504, detail="marketplace_timeout")
    if isinstance(exc, MarketplaceUnreachableError):
        return HTTPException(status_code=502, detail="marketplace_unreachable")
    # Should never reach here; translate to 502 to avoid leaking internals.
    log.warning("unexpected_marketplace_error", error=str(exc))
    return HTTPException(status_code=502, detail="marketplace_unreachable")


def _cache_key(*parts: Any) -> tuple:
    return tuple(parts)


async def _get_repo_node(repository_id: str) -> InfrahubNode | None:
    sdk = get_client()
    try:
        return await sdk.get(kind=InfrahubKind.REPOSITORY, id=repository_id)
    except Exception:  # noqa: BLE001
        return None


async def _list_all_repo_identifiers() -> set[tuple[str, str]]:
    """Return ``{(namespace, name)}`` tuples of schemas already committed in any writable repo.

    Best-effort: we look for ``schemas/<name>.yml`` and ``schemas/<collection>/<name>.yml``
    by listing the configured ``CoreRepository`` nodes and reading the most recent commit.
    When this becomes expensive, cache it.
    """
    # For MVP we return an empty set — the frontend's "already installed" badge is enriched
    # lazily via a dedicated hook that reads the repository's file tree. Keeping the hot
    # path cheap; enrichment lives in follow-up work (see plan.md scope risk #3).
    return set()


# --- Endpoints ---


@router.get("/status", response_model=MarketplaceStatus)
async def get_status(
    _: "AccountSession" = Depends(get_current_user),
) -> MarketplaceStatus:
    """Report proxy configuration + upstream reachability (contracts §7)."""
    url = (config.SETTINGS.marketplace.url or "").strip()
    url_configured = bool(url)
    url_scheme_valid = url_configured and (url.startswith("http://") or url.startswith("https://"))
    upstream_reachable = False
    if url_scheme_valid:
        try:
            async with make_marketplace_client() as client:
                upstream_reachable = await client.ping()
        except MarketplaceMisconfiguredError:
            url_scheme_valid = False
    return MarketplaceStatus(
        marketplace_url=url,
        url_configured=url_configured,
        url_scheme_valid=url_scheme_valid,
        upstream_reachable=upstream_reachable,
        checked_at=datetime.now(timezone.utc),
    )


@router.get("/schemas", response_model=MarketplaceSchemasListResponse)
async def list_schemas(
    search: str | None = None,
    tags: str | None = Query(default=None, description="Comma-separated tag slugs"),
    limit: int = Query(default=20, ge=1, le=50),
    after: str | None = None,
    _: "AccountSession" = Depends(get_current_user),
) -> MarketplaceSchemasListResponse:
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    key = _cache_key("schemas", search, tuple(tag_list or ()), limit, after)
    now = time.monotonic()
    cached = _cache_schemas_list.get(key)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]
    try:
        async with make_marketplace_client() as client:
            result = await client.list_schemas(search=search, tags=tag_list, limit=limit, after=after)
    except Exception as exc:
        raise _map_upstream_error(exc) from exc
    _cache_schemas_list[key] = (now, result)
    return result


@router.get("/schemas/versions/{version_id}/content", response_model=MarketplaceVersionContent)
async def get_schema_version_content(
    version_id: str,
    _: "AccountSession" = Depends(get_current_user),
) -> MarketplaceVersionContent:
    try:
        async with make_marketplace_client() as client:
            return await client.fetch_schema_version_content(version_id=version_id)
    except Exception as exc:
        raise _map_upstream_error(exc) from exc


@router.get("/schemas/{namespace}/{name}", response_model=MarketplaceSchemaDetail)
async def get_schema(
    namespace: str,
    name: str,
    _: "AccountSession" = Depends(get_current_user),
) -> MarketplaceSchemaDetail:
    try:
        async with make_marketplace_client() as client:
            return await client.get_schema(namespace=namespace, name=name)
    except Exception as exc:
        raise _map_upstream_error(exc) from exc


@router.get("/collections", response_model=MarketplaceCollectionsListResponse)
async def list_collections(
    search: str | None = None,
    tags: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    after: str | None = None,
    _: "AccountSession" = Depends(get_current_user),
) -> MarketplaceCollectionsListResponse:
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    key = _cache_key("collections", search, tuple(tag_list or ()), limit, after)
    now = time.monotonic()
    cached = _cache_collections_list.get(key)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]
    try:
        async with make_marketplace_client() as client:
            result = await client.list_collections(search=search, tags=tag_list, limit=limit, after=after)
    except Exception as exc:
        raise _map_upstream_error(exc) from exc
    _cache_collections_list[key] = (now, result)
    return result


@router.get("/collections/{namespace}/{name}", response_model=MarketplaceCollectionDetail)
async def get_collection(
    namespace: str,
    name: str,
    _: "AccountSession" = Depends(get_current_user),
) -> MarketplaceCollectionDetail:
    try:
        async with make_marketplace_client() as client:
            return await client.get_collection(namespace=namespace, name=name)
    except Exception as exc:
        raise _map_upstream_error(exc) from exc


@router.get("/tags", response_model=MarketplaceTagsResponse)
async def list_tags(
    _: "AccountSession" = Depends(get_current_user),
) -> MarketplaceTagsResponse:
    global _cache_tags
    now = time.monotonic()
    if _cache_tags and (now - _cache_tags[0]) < _CACHE_TTL_SECONDS:
        return _cache_tags[1]
    try:
        async with make_marketplace_client() as client:
            result = await client.list_tags()
    except Exception as exc:
        raise _map_upstream_error(exc) from exc
    _cache_tags = (now, result)
    return result


@router.post("/install", response_model=MarketplaceInstallResponse, status_code=202)
async def install(
    request: MarketplaceInstallRequest,
    session: "AccountSession" = Depends(get_current_user),
) -> MarketplaceInstallResponse:
    """Start a Prefect workflow that fetches selected items and applies them.

    Two install paths:

    - ``target="repository"`` (default) — clone the target ``CoreRepository``,
      commit schema files under ``schemas/``, and push. Infrahub's repo-sync
      then loads the schema into the graph. Version-controlled; requires a
      writable repo. Enforces the write-target gate server-side (FR-025,
      FR-027): 404 if the repo doesn't resolve, 409 if it's a
      ``CoreReadOnlyRepository``.
    - ``target="direct"`` — apply schemas to the target branch via the
      schema-load API. No repository, no commit. Faster, no version control;
      the repository-target path is recommended for users who plan to edit
      schemas later via proposed changes.
    """
    workflow = get_workflow()

    if request.target == "repository":
        if not request.repository_id:
            raise HTTPException(status_code=400, detail="repository_id_required_for_repository_target")
        repo_node = await _get_repo_node(request.repository_id)
        if repo_node is None:
            raise HTTPException(status_code=404, detail="repository_not_found")
        kind_name = repo_node._schema.kind if hasattr(repo_node, "_schema") else str(repo_node.__class__.__name__)
        if kind_name == InfrahubKind.READONLYREPOSITORY:
            raise HTTPException(status_code=409, detail="repository_not_writable")

        repo_payload = MarketplaceInstallPayload(
            marketplace_url=config.SETTINGS.marketplace.url,
            initiator_username=session.account_id,  # TODO: resolve display name via the graph
            initiator_user_id=session.account_id,
            repository_id=request.repository_id,
            branch_name=request.branch_name,
            items=list(request.items),
        )
        info = await workflow.submit_workflow(
            workflow=MARKETPLACE_SCHEMA_INSTALL,
            parameters={"payload": repo_payload.model_dump(mode="json")},
        )
        message = "Install queued; poll task status for progress."
    else:  # target == "direct"
        direct_payload = MarketplaceInstallDirectPayload(
            marketplace_url=config.SETTINGS.marketplace.url,
            initiator_username=session.account_id,
            initiator_user_id=session.account_id,
            branch_name=request.branch_name,
            items=list(request.items),
        )
        info = await workflow.submit_workflow(
            workflow=MARKETPLACE_SCHEMA_INSTALL_DIRECT,
            parameters={"payload": direct_payload.model_dump(mode="json")},
        )
        message = "Direct install queued; schemas will be applied via the schema-load API."

    task_id = str(getattr(info, "id", None) or getattr(info, "flow_run_id", None) or UUIDT().new())
    return MarketplaceInstallResponse(task_id=task_id, message=message)


@router.get("/cli-snippet", response_model=CliSnippetResponse)
async def cli_snippet(
    items: Annotated[list[str], Query(min_length=1, max_length=50)],
    branch_name: str = "main",
    output_dir: str = "./schemas",
    _: "AccountSession" = Depends(get_current_user),
) -> CliSnippetResponse:
    """Render copy-pasteable `infrahubctl marketplace download` + `infrahubctl schema load` commands."""
    try:
        parsed_items: list[MarketplaceInstallItem] = [parse_install_item(token) for token in items]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid_item: {exc}") from exc
    try:
        return render_cli_snippet(
            items=parsed_items,
            branch_name=branch_name,
            output_dir=output_dir,
            marketplace_url=config.SETTINGS.marketplace.url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
