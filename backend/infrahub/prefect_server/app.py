from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import sqlalchemy as sa
from fastapi import APIRouter, FastAPI
from prefect.context import refresh_global_settings_context
from prefect.server.api.server import create_app
from prefect.server.database import provide_database_interface
from prefect.server.database.configurations import AsyncPostgresConfiguration
from prefect.settings import get_current_settings
from pydantic import ValidationError

from . import events, task_history
from .bootstrap import init_prefect
from .database import read_stored_event_types
from .retention import (
    apply_prefect_retention_env,
    background_services_warning,
    event_types_with_retention_override,
    prefect_retention_already_set,
    prefect_retention_in_effect,
    remove_blank_vacuum_switch,
    turned_off_cleanup_warnings,
    unlisted_prefect_event_types_warning,
)
from .retention_settings import load_task_manager_settings, print_configuration_errors

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from prefect.server.database import PrefectDBInterface

log = logging.getLogger(__name__)

# The task manager serves no request until the check ends, so a locked events table delays its start by at most this long.
_STORED_EVENT_TYPES_TIME_LIMIT = "5s"

router = APIRouter(prefix="/infrahub")

router.include_router(events.router)
router.include_router(task_history.router)


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
    """Read the task manager section of Infrahub's configuration into Prefect's retention settings and log them, exiting when it is invalid."""
    # Sets up the log handler and level that the retention lines need, and is imported here because the stock
    # Prefect container of some test suites has no infrahub package.
    import infrahub.log  # noqa: F401, PLC0415

    config_file = Path(os.environ.get("INFRAHUB_CONFIG", "infrahub.toml")).resolve()
    try:
        retention = load_task_manager_settings(config_file=config_file).retention
    except ValidationError as error:
        print_configuration_errors(error=error)
        sys.exit(1)
    remove_blank_vacuum_switch(environ=os.environ)
    # Read before any write, since a variable written here would count as one the operator set.
    already_set = prefect_retention_already_set()
    for warning in apply_prefect_retention_env(environ=os.environ, settings=retention, already_set=already_set):
        log.warning(warning)
    # Prefect reads its settings from the environment once at import, so new values apply only after a refresh.
    refresh_global_settings_context()
    prefect_settings = get_current_settings()
    for warning in turned_off_cleanup_warnings(vacuum=prefect_settings.server.services.db_vacuum):
        log.warning(warning)
    for name, value in prefect_retention_in_effect(settings=prefect_settings).items():
        log.info(f"Task manager retention: {name}={value}")


async def warn_about_unlisted_prefect_event_types(db: PrefectDBInterface) -> None:
    """Log the stored Prefect event types that have no per-type retention, which the event retention keeps."""
    settings = get_current_settings()
    overridden = event_types_with_retention_override(settings=settings)
    # Without a per-type retention shorter than the event retention, Prefect keeps every event type for the same time.
    if not overridden:
        return
    try:
        async with db.session_context() as session:
            if isinstance(db.database_config, AsyncPostgresConfiguration):
                # Local to the read's transaction, so the pooled connection goes back to Prefect with its own limit.
                await session.execute(
                    sa.select(sa.func.set_config("statement_timeout", _STORED_EVENT_TYPES_TIME_LIMIT, sa.true()))
                )
            stored = await read_stored_event_types(session=session)
    # A best-effort check: no error from the database or its driver may keep the task manager from starting.
    except Exception:
        log.warning(
            "Task manager retention: could not read the stored event types, so the check for Prefect event types "
            "without a per-type retention was skipped",
            exc_info=True,
        )
        return
    if warning := unlisted_prefect_event_types_warning(
        stored_event_types=stored, overridden=overridden, event_retention=settings.server.events.retention_period
    ):
        log.warning(warning)


@asynccontextmanager
async def _check_stored_event_types(_app: FastAPI) -> AsyncGenerator[None]:
    await warn_about_unlisted_prefect_event_types(db=provide_database_interface())
    yield


def create_prefect_app_with_infrahub_routes() -> FastAPI:
    """Build Prefect's server app with Infrahub's routes, leaving Prefect's settings as the environment sets them."""
    app = create_app()
    api_app: FastAPI = app.__dict__["api_app"]
    api_app.include_router(router=router)

    return app


def create_infrahub_prefect() -> FastAPI:
    """Build the task manager app with Prefect's settings derived from Infrahub's configuration."""
    apply_infrahub_settings_to_prefect()
    if warning := background_services_warning(environ=os.environ):
        log.warning(warning)

    if (
        os.getenv("PREFECT_API_BLOCKS_REGISTER_ON_START") == "false"
        and os.getenv("PREFECT_API_DATABASE_MIGRATE_ON_START") == "false"
    ):
        # We are probably running distributed mode
        from infrahub import config  # noqa: PLC0415

        config.SETTINGS.initialize_and_exit()
        asyncio.run(_init_prefect())

    app = create_prefect_app_with_infrahub_routes()
    # FastAPI enters an included router's lifespan after the app's own, so the read runs once Prefect's startup has migrated the database.
    app.include_router(APIRouter(lifespan=_check_stored_event_types))
    return app
