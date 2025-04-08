import logging
import os
import time
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from typing import AsyncGenerator, Awaitable, Callable

from asgi_correlation_id import CorrelationIdMiddleware
from asgi_correlation_id.context import correlation_id
from fastapi import FastAPI, Request, Response
from fastapi.logger import logger
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from infrahub_sdk.exceptions import TimestampFormatError
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.trace import Span
from starlette_exporter import PrometheusMiddleware, handle_metrics

from infrahub import __version__, config
from infrahub.api import router as api
from infrahub.api.exception_handlers import generic_api_exception_handler
from infrahub.components import ComponentType
from infrahub.core.graph.index import node_indexes, rel_indexes
from infrahub.core.initialization import initialization
from infrahub.database import InfrahubDatabase, InfrahubDatabaseMode, get_db
from infrahub.dependencies.registry import build_component_registry
from infrahub.exceptions import Error, ValidationError
from infrahub.graphql.api.endpoints import router as graphql_router
from infrahub.lock import initialize_lock
from infrahub.log import clear_log_context, get_logger, set_log_data
from infrahub.middleware import InfrahubCORSMiddleware
from infrahub.services import InfrahubServices
from infrahub.services.adapters.cache import InfrahubCache
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.trace import add_span_exception, configure_trace, get_traceid
from infrahub.worker import WORKER_IDENTITY

CURRENT_DIRECTORY = Path(__file__).parent.resolve()


async def app_initialization(application: FastAPI, enable_scheduler: bool = True) -> None:
    config.SETTINGS.initialize_and_exit()

    # Initialize trace
    if config.SETTINGS.trace.enable:
        configure_trace(
            service="infrahub-server",
            version=__version__,
            exporter_type=config.SETTINGS.trace.exporter_type,
            exporter_endpoint=config.SETTINGS.trace.exporter_endpoint,
            exporter_protocol=config.SETTINGS.trace.exporter_protocol,
        )

    # Initialize database Driver and load local registry
    database = application.state.db = InfrahubDatabase(mode=InfrahubDatabaseMode.DRIVER, driver=await get_db())
    database.manager.index.init(nodes=node_indexes, rels=rel_indexes)

    build_component_registry()

    workflow = config.OVERRIDE.workflow or (
        WorkflowWorkerExecution()
        if config.SETTINGS.workflow.driver == config.WorkflowDriver.WORKER
        else WorkflowLocalExecution()
    )
    component_type = ComponentType.API_SERVER
    message_bus = config.OVERRIDE.message_bus or await InfrahubMessageBus.new_from_driver(
        component_type=component_type, driver=config.SETTINGS.broker.driver
    )

    cache = config.OVERRIDE.cache or (await InfrahubCache.new_from_driver(driver=config.SETTINGS.cache.driver))
    service = await InfrahubServices.new(
        cache=cache,
        database=database,
        message_bus=message_bus,
        workflow=workflow,
        component_type=component_type,
    )
    initialize_lock(service=service)
    # We must initialize DB after initialize lock and initialize lock depends on cache initialization
    async with application.state.db.start_session() as db:
        await initialization(db=db)

    application.state.service = service
    application.state.response_delay = config.SETTINGS.miscellaneous.response_delay
    if enable_scheduler:
        await service.scheduler.start_schedule()


async def shutdown(application: FastAPI) -> None:
    await application.state.service.shutdown()
    await application.state.db.close()


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator:
    await app_initialization(application)
    yield
    await shutdown(application)


app = FastAPI(
    title="Infrahub",
    version=__version__,
    lifespan=lifespan,
    openapi_url="/api/openapi.json",
    docs_url=None,
    redoc_url=None,
)


def server_request_hook(span: Span, scope: dict) -> None:  # noqa: ARG001
    if span and span.is_recording():
        span.set_attribute("worker", WORKER_IDENTITY)


FastAPIInstrumentor().instrument_app(app, excluded_urls=".*/metrics", server_request_hook=server_request_hook)

FRONTEND_DIRECTORY = Path(os.environ.get("INFRAHUB_FRONTEND_DIRECTORY", "frontend/app")).resolve()
FRONTEND_ASSET_DIRECTORY = FRONTEND_DIRECTORY / "dist" / "assets"
FRONTEND_FAVICONS_DIRECTORY = FRONTEND_DIRECTORY / "dist" / "favicons"

DOCS_DIRECTORY = Path(os.environ.get("INFRAHUB_DOCS_DIRECTORY", Path("docs").resolve()))
DOCS_BUILD_DIRECTORY = DOCS_DIRECTORY / "build"

log = get_logger()
gunicorn_logger = logging.getLogger("gunicorn.error")
logger.handlers = gunicorn_logger.handlers

app.include_router(api)

templates = Jinja2Templates(directory=FRONTEND_DIRECTORY / "dist")


@app.middleware("http")
async def logging_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    clear_log_context()
    request_id = correlation_id.get()

    set_log_data(key="request_id", value=request_id)
    set_log_data(key="app", value="infrahub.api")
    set_log_data(key="worker", value=WORKER_IDENTITY)

    trace_id = get_traceid()
    if trace_id:
        set_log_data(key="trace_id", value=trace_id)

    response = await call_next(request)
    return response


@app.middleware("http")
async def add_process_time_header(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.middleware("http")
async def add_telemetry_span_exception(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    try:
        return await call_next(request)
    except Exception as exc:
        add_span_exception(exc)
        raise


app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    PrometheusMiddleware,
    app_name="infrahub",
    group_paths=True,
    prefix="infrahub",
    buckets=[0.1, 0.25, 0.5],
    skip_paths=["/health"],
)
app.add_middleware(InfrahubCORSMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=100_000)

app.add_exception_handler(Error, generic_api_exception_handler)
app.add_exception_handler(TimestampFormatError, partial(generic_api_exception_handler, http_code=400))
app.add_exception_handler(ValidationError, partial(generic_api_exception_handler, http_code=400))

app.add_route(path="/metrics", route=handle_metrics)
app.include_router(graphql_router)

app.mount("/api-static", StaticFiles(directory=CURRENT_DIRECTORY / "api" / "static"), name="static")

if FRONTEND_ASSET_DIRECTORY.exists() and FRONTEND_ASSET_DIRECTORY.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSET_DIRECTORY), "assets")


if FRONTEND_FAVICONS_DIRECTORY.exists() and FRONTEND_FAVICONS_DIRECTORY.is_dir():
    app.mount("/favicons", StaticFiles(directory=FRONTEND_FAVICONS_DIRECTORY), "favicons")


if DOCS_BUILD_DIRECTORY.exists() and DOCS_BUILD_DIRECTORY.is_dir():
    app.mount("/docs", StaticFiles(directory=DOCS_BUILD_DIRECTORY, html=True, check_dir=True), name="infrahub-docs")


@app.get("/docs", include_in_schema=False)
async def documentation() -> RedirectResponse:
    return RedirectResponse("/docs/")


@app.get("/{rest_of_path:path}", include_in_schema=False)
async def react_app(req: Request, rest_of_path: str) -> Response:  # noqa: ARG001
    return templates.TemplateResponse("index.html", {"request": req})
