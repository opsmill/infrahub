from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, FastAPI
from prefect.server.api.server import create_app

from . import events
from .bootstrap import init_prefect

GLOBAL_TASKMGR_INIT_LOCK = "global.taskmgr.init"

router = APIRouter(prefix="/infrahub")

router.include_router(events.router)


async def _init_prefect() -> None:
    # Import there in case we are running Prefect within a testsuite using the original Prefect container
    from infrahub import lock
    from infrahub.lock import initialize_lock
    from infrahub.services import InfrahubServices
    from infrahub.workers.dependencies import get_cache

    cache = await get_cache()
    service = await InfrahubServices.new(cache=cache)
    initialize_lock(service=service)

    async with lock.registry.get(name=GLOBAL_TASKMGR_INIT_LOCK):
        await init_prefect()


def create_infrahub_prefect() -> FastAPI:
    if (
        os.getenv("PREFECT_API_BLOCKS_REGISTER_ON_START") == "false"
        and os.getenv("PREFECT_API_DATABASE_MIGRATE_ON_START") == "false"
    ):
        # We are probably running distributed mode
        from infrahub import config

        config.SETTINGS.initialize_and_exit()
        asyncio.run(_init_prefect())

    app = create_app()
    api_app: FastAPI = app.__dict__["api_app"]
    api_app.include_router(router=router)

    return app
