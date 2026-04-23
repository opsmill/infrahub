"""REST proxy endpoints for `marketplace.infrahub.app`.

Frontend never calls the Marketplace directly (CORS constraint); all traffic
flows through this proxy. Endpoints require authentication via `get_current_user`;
writing endpoints additionally require the Infrahub permissions that gate the
eventual side effect (`MANAGE_SCHEMA`, plus `MANAGE_REPOSITORIES` for the
repository-target install path).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query

from infrahub import config
from infrahub.api.dependencies import get_current_user, get_db
from infrahub.core import registry
from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GLOBAL_BRANCH_NAME, GlobalPermissions, InfrahubKind, PermissionDecision
from infrahub.database import InfrahubDatabase  # noqa: TC001
from infrahub.log import get_logger
from infrahub.marketplace.cli_snippet import parse_install_item, render_cli_snippet
from infrahub.marketplace.client import (
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
from infrahub.permissions import PermissionManager, define_global_permission_from_branch
from infrahub.workers.dependencies import get_client, get_workflow
from infrahub.workflows.catalogue import MARKETPLACE_SCHEMA_INSTALL, MARKETPLACE_SCHEMA_INSTALL_DIRECT

if TYPE_CHECKING:
    from infrahub.auth import AccountSession

log = get_logger()

router = APIRouter(prefix="/marketplace", tags=["marketplace"])

_CACHE_TTL_SECONDS = 30.0
_CACHE_MAX_ENTRIES = 128
_cache_schemas_list: TTLCache[tuple, MarketplaceSchemasListResponse] = TTLCache(
    maxsize=_CACHE_MAX_ENTRIES, ttl=_CACHE_TTL_SECONDS
)
_cache_collections_list: TTLCache[tuple, MarketplaceCollectionsListResponse] = TTLCache(
    maxsize=_CACHE_MAX_ENTRIES, ttl=_CACHE_TTL_SECONDS
)
_cache_tags: TTLCache[str, MarketplaceTagsResponse] = TTLCache(maxsize=1, ttl=_CACHE_TTL_SECONDS)
_cache_status: TTLCache[str, MarketplaceStatus] = TTLCache(maxsize=1, ttl=_CACHE_TTL_SECONDS)


def _map_upstream_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MarketplaceMisconfiguredError):
        return HTTPException(status_code=500, detail="marketplace_misconfigured")
    if isinstance(exc, MarketplaceNotFoundError):
        return HTTPException(status_code=404, detail="not_found")
    if isinstance(exc, MarketplaceTimeoutError):
        return HTTPException(status_code=504, detail="marketplace_timeout")
    if isinstance(exc, MarketplaceUnreachableError):
        return HTTPException(status_code=502, detail="marketplace_unreachable")
    log.warning("unexpected_marketplace_error", error=str(exc))
    return HTTPException(status_code=502, detail="marketplace_unreachable")


def _cache_key(*parts: Any) -> tuple:
    return tuple(parts)


async def _assert_writable_repo(repository_id: str) -> None:
    """Raise 404 if the repo doesn't resolve, 409 if it's a CoreReadOnlyRepository."""
    sdk = get_client()
    readonly = await sdk.get(kind=InfrahubKind.READONLYREPOSITORY, id=repository_id, raise_when_missing=False)
    if readonly is not None:
        raise HTTPException(status_code=409, detail="repository_not_writable")
    writable = await sdk.get(kind=InfrahubKind.REPOSITORY, id=repository_id, raise_when_missing=False)
    if writable is None:
        raise HTTPException(status_code=404, detail="repository_not_found")


async def _resolve_account_name(db: InfrahubDatabase, account_id: str) -> str:
    """Look up the account's name for audit trails (commit author, flow artifact).

    Falls back to the UUID if the account can't be resolved -- the install flow
    must still succeed even if the account node is missing for some reason.
    """
    from infrahub.core.manager import NodeManager
    from infrahub.core.protocols import CoreGenericAccount

    try:
        account = await NodeManager.get_one(db=db, kind=CoreGenericAccount, id=account_id)
    except Exception:  # noqa: BLE001
        log.warning("marketplace_install_account_lookup_failed", account_id=account_id)
        return account_id
    if account is None:
        return account_id
    return account.name.value or account_id


# --- Endpoints ---


@router.get("/status", response_model=MarketplaceStatus)
async def get_status(
    _: AccountSession = Depends(get_current_user),
) -> MarketplaceStatus:
    """Report proxy configuration + upstream reachability (contracts §7)."""
    cached = _cache_status.get("status")
    if cached is not None:
        return cached

    url = (config.SETTINGS.marketplace.url or "").strip()
    url_configured = bool(url)
    url_scheme_valid = url_configured and url.startswith(("http://", "https://"))
    upstream_reachable = False
    if url_scheme_valid:
        try:
            async with make_marketplace_client() as client:
                upstream_reachable = await client.ping()
        except MarketplaceMisconfiguredError:
            url_scheme_valid = False
    result = MarketplaceStatus(
        marketplace_url=url,
        url_configured=url_configured,
        url_scheme_valid=url_scheme_valid,
        upstream_reachable=upstream_reachable,
        checked_at=datetime.now(UTC),
    )
    _cache_status["status"] = result
    return result


@router.get("/schemas", response_model=MarketplaceSchemasListResponse)
async def list_schemas(
    search: str | None = None,
    tags: str | None = Query(default=None, description="Comma-separated tag slugs"),
    limit: int = Query(default=20, ge=1, le=50),
    after: str | None = None,
    _: AccountSession = Depends(get_current_user),
) -> MarketplaceSchemasListResponse:
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    key = _cache_key("schemas", search, tuple(tag_list or ()), limit, after)
    cached = _cache_schemas_list.get(key)
    if cached is not None:
        return cached
    try:
        async with make_marketplace_client() as client:
            result = await client.list_schemas(search=search, tags=tag_list, limit=limit, after=after)
    except Exception as exc:
        raise _map_upstream_error(exc) from exc
    _cache_schemas_list[key] = result
    return result


@router.get("/schemas/versions/{version_id}/content", response_model=MarketplaceVersionContent)
async def get_schema_version_content(
    version_id: str,
    _: AccountSession = Depends(get_current_user),
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
    _: AccountSession = Depends(get_current_user),
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
    _: AccountSession = Depends(get_current_user),
) -> MarketplaceCollectionsListResponse:
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    key = _cache_key("collections", search, tuple(tag_list or ()), limit, after)
    cached = _cache_collections_list.get(key)
    if cached is not None:
        return cached
    try:
        async with make_marketplace_client() as client:
            result = await client.list_collections(search=search, tags=tag_list, limit=limit, after=after)
    except Exception as exc:
        raise _map_upstream_error(exc) from exc
    _cache_collections_list[key] = result
    return result


@router.get("/collections/{namespace}/{name}", response_model=MarketplaceCollectionDetail)
async def get_collection(
    namespace: str,
    name: str,
    _: AccountSession = Depends(get_current_user),
) -> MarketplaceCollectionDetail:
    try:
        async with make_marketplace_client() as client:
            return await client.get_collection(namespace=namespace, name=name)
    except Exception as exc:
        raise _map_upstream_error(exc) from exc


@router.get("/tags", response_model=MarketplaceTagsResponse)
async def list_tags(
    _: AccountSession = Depends(get_current_user),
) -> MarketplaceTagsResponse:
    cached = _cache_tags.get("tags")
    if cached is not None:
        return cached
    try:
        async with make_marketplace_client() as client:
            result = await client.list_tags()
    except Exception as exc:
        raise _map_upstream_error(exc) from exc
    _cache_tags["tags"] = result
    return result


async def _build_permission_manager(
    db: InfrahubDatabase, session: AccountSession, branch_name: str
) -> PermissionManager:
    """Build a PermissionManager scoped to the branch referenced in the install payload.

    The default `get_permission_manager` dependency reads `?branch=` from the
    query string; we need to gate on the branch the user is *installing into*,
    which lives in the request body.
    """
    branch = await registry.get_branch(db=db, branch=branch_name)
    permission_manager = PermissionManager(account_session=session)
    await permission_manager.load_permissions(db=db, branch=branch)
    return permission_manager


def _raise_for_install_permissions(permission_manager: PermissionManager, target: str, branch_name: str) -> None:
    """Enforce the permissions that match what the install will actually do.

    Both paths end in a schema mutation, so both require MANAGE_SCHEMA. The
    repository target additionally performs a git push against a CoreRepository
    node, so it requires MANAGE_REPOSITORIES. Installing into main/global
    further requires EDIT_DEFAULT_BRANCH, mirroring `/api/schema/load`.
    """
    permission_manager.raise_for_permission(
        permission=define_global_permission_from_branch(
            permission=GlobalPermissions.MANAGE_SCHEMA, branch_name=branch_name
        )
    )
    if target == "repository":
        permission_manager.raise_for_permission(
            permission=define_global_permission_from_branch(
                permission=GlobalPermissions.MANAGE_REPOSITORIES, branch_name=branch_name
            )
        )
    if branch_name in (GLOBAL_BRANCH_NAME, registry.default_branch):
        permission_manager.raise_for_permission(
            permission=GlobalPermission(
                action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value,
                decision=PermissionDecision.ALLOW_DEFAULT.value,
            ),
        )


@router.post("/install", response_model=MarketplaceInstallResponse, status_code=202)
async def install(
    request: MarketplaceInstallRequest,
    session: AccountSession = Depends(get_current_user),
    db: InfrahubDatabase = Depends(get_db),
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
    permission_manager = await _build_permission_manager(db=db, session=session, branch_name=request.branch_name)
    _raise_for_install_permissions(
        permission_manager=permission_manager, target=request.target, branch_name=request.branch_name
    )

    initiator_username = await _resolve_account_name(db=db, account_id=session.account_id)
    workflow = get_workflow()

    if request.target == "repository":
        # Router-side assertion; the Pydantic model also enforces this via
        # model_validator(mode="after") — kept as belt-and-braces since the
        # HTTP surface wants an explicit 400 code, not a 422 ValidationError.
        if not request.repository_id:
            raise HTTPException(status_code=400, detail="repository_id_required_for_repository_target")
        await _assert_writable_repo(request.repository_id)

        repo_payload = MarketplaceInstallPayload(
            marketplace_url=config.SETTINGS.marketplace.url,
            initiator_username=initiator_username,
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
            initiator_username=initiator_username,
            initiator_user_id=session.account_id,
            branch_name=request.branch_name,
            items=list(request.items),
        )
        info = await workflow.submit_workflow(
            workflow=MARKETPLACE_SCHEMA_INSTALL_DIRECT,
            parameters={"payload": direct_payload.model_dump(mode="json")},
        )
        message = "Direct install queued; schemas will be applied via the schema-load API."

    task_id = getattr(info, "id", None) or getattr(info, "flow_run_id", None)
    if task_id is None:
        log.error("marketplace_install_missing_task_id", target=request.target)
        raise HTTPException(status_code=500, detail="workflow_did_not_return_task_id")
    return MarketplaceInstallResponse(task_id=str(task_id), message=message)


@router.get("/cli-snippet", response_model=CliSnippetResponse)
async def cli_snippet(
    items: Annotated[list[str], Query(min_length=1, max_length=50)],
    branch_name: str = "main",
    output_dir: str = "./schemas",
    _: AccountSession = Depends(get_current_user),
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
