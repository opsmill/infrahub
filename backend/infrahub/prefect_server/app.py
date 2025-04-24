from __future__ import annotations

import importlib.metadata
import os

from fastapi import APIRouter, FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prefect.server.api.server import create_app

from infrahub import config
from infrahub.trace import configure_trace

from . import events

router = APIRouter(prefix="/infrahub")

router.include_router(events.router)


def create_infrahub_prefect() -> FastAPI:
    if not config.SETTINGS.settings:
        config_file = os.environ.get("INFRAHUB_CONFIG", "infrahub.toml")
        config.load_and_exit(config_file_name=config_file)

    # Initialize trace
    if config.SETTINGS.trace.enable:
        configure_trace(
            service="prefect-server",
            version=importlib.metadata.version("prefect"),
            exporter_type=config.SETTINGS.trace.exporter_type,
            exporter_endpoint=config.SETTINGS.trace.exporter_endpoint,
            exporter_protocol=config.SETTINGS.trace.exporter_protocol,
        )

    app = create_app()
    api_app: FastAPI = app.__dict__["api_app"]
    api_app.include_router(router=router)

    FastAPIInstrumentor.instrument_app(api_app)

    return app
