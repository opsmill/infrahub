from __future__ import annotations

import asyncio
import logging
import os

from fastapi import APIRouter, FastAPI
from prefect.context import refresh_global_settings_context
from prefect.server.api.server import create_app

from . import events
from .bootstrap import init_prefect
from .retention import apply_prefect_retention_env, prefect_retention_env_in_effect

log = logging.getLogger(__name__)

router = APIRouter(prefix="/infrahub")

router.include_router(events.router)


async def _init_prefect() -> None:
    # Import there in case we are running Prefect within a testsuite using the original Prefect container
    from infrahub import lock  # noqa: PLC0415
    from infrahub.lock import initialize_lock  # noqa: PLC0415
    from infrahub.services import InfrahubServices  # noqa: PLC0415
    from infrahub.workers.dependencies import get_cache  # noqa: PLC0415

    cache = await get_cache()
    service = await InfrahubServices.new(cache=cache)
    initialize_lock(service=service)

    async with lock.registry.get(name=lock.GLOBAL_TASKMGR_INIT_LOCK):
        await init_prefect()


def apply_infrahub_settings_to_prefect() -> None:
    """Load Infrahub's configuration into Prefect's retention settings and log them, exiting when it is invalid."""
    # The original Prefect container used by some test suites has no infrahub package.
    from infrahub import config  # noqa: PLC0415

    config.SETTINGS.initialize_and_exit()
    for warning in apply_prefect_retention_env(environ=os.environ, settings=config.SETTINGS.task_manager.retention):
        log.warning(warning)
    # Prefect reads its settings from the environment once at import, so new values apply only after a refresh.
    refresh_global_settings_context()
    for name, value in prefect_retention_env_in_effect(environ=os.environ).items():
        log.info(f"Task manager retention: {name}={value}")


def create_prefect_app_with_infrahub_routes() -> FastAPI:
    """Build Prefect's server app with Infrahub's routes, leaving Prefect's settings as the environment sets them."""
    app = create_app()
    api_app: FastAPI = app.__dict__["api_app"]
    api_app.include_router(router=router)

    return app


def create_infrahub_prefect() -> FastAPI:
    """Build the task manager app with Prefect's settings derived from Infrahub's configuration."""
    apply_infrahub_settings_to_prefect()

    if (
        os.getenv("PREFECT_API_BLOCKS_REGISTER_ON_START") == "false"
        and os.getenv("PREFECT_API_DATABASE_MIGRATE_ON_START") == "false"
    ):
        # We are probably running distributed mode
        asyncio.run(_init_prefect())

    return create_prefect_app_with_infrahub_routes()
