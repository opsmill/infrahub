from typing import NoReturn

from fastapi import APIRouter

from infrahub.api import (
    artifact,
    auth,
    diff,
    file,
    internal,
    menu,
    query,
    schema,
    storage,
    transformation,
)
from infrahub.exceptions import NodeNotFound

router = APIRouter(prefix="/api")

router.include_router(artifact.router)
router.include_router(auth.router)
router.include_router(diff.router)
router.include_router(file.router)
router.include_router(internal.router)
router.include_router(menu.router)
router.include_router(query.router)
router.include_router(schema.router)
router.include_router(storage.router)
router.include_router(transformation.router)


@router.api_route(
    "/{rest_of_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    include_in_schema=False,
    response_model=None,
)
async def not_found(rest_of_path: str) -> NoReturn:
    """Used to avoid having the mounting of the React App mask 404 errors."""
    raise NodeNotFound(
        node_type="url",
        identifier=f"/api/{rest_of_path}",
        message=f"The requested endpoint /api/{rest_of_path} does not exist",
    )
