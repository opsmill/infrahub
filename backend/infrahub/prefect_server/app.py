from __future__ import annotations

from fastapi import APIRouter, FastAPI
from prefect.server.api.server import create_app

from . import events

router = APIRouter(prefix="/infrahub")

router.include_router(events.router)


def create_infrahub_prefect() -> FastAPI:
    app = create_app()
    api_app: FastAPI = app.__dict__["api_app"]
    api_app.include_router(router=router)

    return app
