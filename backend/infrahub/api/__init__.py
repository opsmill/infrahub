from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

from fastapi import APIRouter, Depends
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
)
from starlette.responses import HTMLResponse  # noqa: TC002

from infrahub.api import (
    artifact,
    auth,
    diff,
    file,
    internal,
    menu,
    oauth2,
    oidc,
    query,
    schema,
    storage,
    transformation,
)
from infrahub.api.dependencies import get_current_user
from infrahub.exceptions import ResourceNotFoundError

if TYPE_CHECKING:
    from infrahub.auth import AccountSession

router = APIRouter(prefix="/api")

router.include_router(artifact.router)
router.include_router(auth.router)
router.include_router(diff.router)
router.include_router(file.router)
router.include_router(internal.router)
router.include_router(menu.router)
router.include_router(oauth2.router)
router.include_router(oidc.router)
router.include_router(query.router)
router.include_router(schema.router)
router.include_router(storage.router)
router.include_router(transformation.router)


@router.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html(
    _: AccountSession = Depends(get_current_user),
) -> HTMLResponse:
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title="Infrahub - Swagger UI",
        swagger_js_url="/api-static/swagger-ui-bundle.js",
        swagger_css_url="/api-static/swagger-ui.css",
    )


@router.get("/redoc", include_in_schema=False)
async def redoc_html(_: AccountSession = Depends(get_current_user)) -> HTMLResponse:
    return get_redoc_html(
        openapi_url="/api/openapi.json",
        title="Infrahub - ReDoc",
        redoc_js_url="/api-static/redoc.standalone.js",
    )


@router.api_route(
    "/{rest_of_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    include_in_schema=False,
    response_model=None,
)
async def not_found(rest_of_path: str) -> NoReturn:
    """Used to avoid having the mounting of the React App mask 404 errors."""
    raise ResourceNotFoundError(
        message=f"The requested endpoint /api/{rest_of_path} does not exist",
    )
