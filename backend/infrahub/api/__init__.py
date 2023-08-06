from fastapi import APIRouter

from infrahub.api import (
    artifact,
    auth,
    check,
    diff,
    file,
    internal,
    query,
    schema,
    storage,
    transformation,
)

router = APIRouter(prefix="/api")

router.include_router(artifact.router)
router.include_router(auth.router)
router.include_router(check.router)
router.include_router(diff.router)
router.include_router(file.router)
router.include_router(internal.router)
router.include_router(query.router)
router.include_router(schema.router)
router.include_router(storage.router)
router.include_router(transformation.router)
