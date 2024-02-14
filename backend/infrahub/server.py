import logging
import os
import time
from contextlib import asynccontextmanager
from functools import partial
from typing import Awaitable, Callable

from asgi_correlation_id import CorrelationIdMiddleware
from asgi_correlation_id.context import correlation_id
from fastapi import FastAPI, Request, Response
from fastapi.logger import logger
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from infrahub_sdk.timestamp import TimestampFormatError
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import ValidationError
from starlette_exporter import PrometheusMiddleware, handle_metrics

from infrahub import __version__, config
from infrahub.api import router as api
from infrahub.api.exception_handlers import generic_api_exception_handler
from infrahub.components import ComponentType
from infrahub.core.initialization import initialization
from infrahub.database import InfrahubDatabase, InfrahubDatabaseMode, get_db
from infrahub.exceptions import Error
from infrahub.graphql.api.endpoints import router as graphql_router
from infrahub.lock import initialize_lock
from infrahub.log import clear_log_context, get_logger, set_log_data
from infrahub.message_bus.rpc import InfrahubRpcClient
from infrahub.middleware import InfrahubCORSMiddleware
from infrahub.services import InfrahubServices, services
from infrahub.services.adapters.cache.redis import RedisCache
from infrahub.services.adapters.message_bus.rabbitmq import RabbitMQMessageBus
from infrahub.trace import add_span_exception, configure_trace, get_traceid, get_tracer
from infrahub.worker import WORKER_IDENTITY


async def app_initialization(application: FastAPI) -> None:
    if not config.SETTINGS:
        config_file_name = os.environ.get("INFRAHUB_CONFIG", "infrahub.toml")
        config_file_path = os.path.abspath(config_file_name)
        log.info("application_init", config_file=config_file_path)
        config.load_and_exit(config_file_path)

    # Initialize trace
    if config.SETTINGS.trace.enable:
        configure_trace(
            version=__version__,
            exporter_type=config.SETTINGS.trace.exporter_type,
            exporter_endpoint=config.SETTINGS.trace.trace_endpoint,
            exporter_protocol=config.SETTINGS.trace.exporter_protocol,
        )

    # Initialize database Driver and load local registry
    database = application.state.db = InfrahubDatabase(mode=InfrahubDatabaseMode.DRIVER, driver=await get_db())

    initialize_lock()

    async with application.state.db.start_session() as db:
        await initialization(db=db)

    message_bus = config.OVERRIDE.message_bus or RabbitMQMessageBus()
    cache = config.OVERRIDE.cache or RedisCache()
    service = InfrahubServices(
        cache=cache, database=database, message_bus=message_bus, component_type=ComponentType.API_SERVER
    )
    await service.initialize()
    services.prepare(service=service)
    # Initialize RPC Client
    rpc_client = InfrahubRpcClient()
    application.state.rpc_client = rpc_client
    application.state.service = service


async def shutdown(application: FastAPI) -> None:
    await services.service.shutdown()
    await application.state.db.close()


@asynccontextmanager
async def lifespan(application: FastAPI):
    await app_initialization(application)
    yield
    await shutdown(application)


app = FastAPI(
    title="Infrahub",
    version=__version__,
    lifespan=lifespan,
    contact={
        "name": "OpsMill",
        "email": "info@opsmill.com",
    },
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

FastAPIInstrumentor().instrument_app(app, excluded_urls=".*/metrics")
tracer = get_tracer()

FRONTEND_DIRECTORY = os.environ.get("INFRAHUB_FRONTEND_DIRECTORY", os.path.abspath("frontend"))
FRONTEND_ASSET_DIRECTORY = f"{FRONTEND_DIRECTORY}/dist/assets"
FRONTEND_FAVICONS_DIRECTORY = f"{FRONTEND_DIRECTORY}/dist/favicons"

DOCS_DIRECTORY = os.environ.get("INFRAHUB_DOCS_DIRECTORY", os.path.abspath("docs"))
DOCS_BUILD_DIRECTORY = f"{DOCS_DIRECTORY}/build"

log = get_logger()
gunicorn_logger = logging.getLogger("gunicorn.error")
logger.handlers = gunicorn_logger.handlers

app.include_router(api)

templates = Jinja2Templates(directory=f"{FRONTEND_DIRECTORY}/dist")


@app.middleware("http")
async def logging_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    clear_log_context()
    request_id = correlation_id.get()
    with tracer.start_as_current_span("processing request " + request_id):
        trace_id = get_traceid()
        set_log_data(key="request_id", value=request_id)
        set_log_data(key="app", value="infrahub.api")
        set_log_data(key="worker", value=WORKER_IDENTITY)
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

app.add_exception_handler(Error, generic_api_exception_handler)
app.add_exception_handler(TimestampFormatError, partial(generic_api_exception_handler, http_code=400))
app.add_exception_handler(ValidationError, partial(generic_api_exception_handler, http_code=400))

app.add_route(path="/metrics", route=handle_metrics)
app.include_router(graphql_router)


if os.path.exists(DOCS_BUILD_DIRECTORY) and os.path.isdir(DOCS_BUILD_DIRECTORY):
    app.mount("/docs", StaticFiles(directory=DOCS_BUILD_DIRECTORY, html=True, check_dir=True), name="infrahub-docs")


if os.path.exists(FRONTEND_ASSET_DIRECTORY) and os.path.isdir(FRONTEND_ASSET_DIRECTORY):
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSET_DIRECTORY), "assets")


if os.path.exists(FRONTEND_FAVICONS_DIRECTORY) and os.path.isdir(FRONTEND_FAVICONS_DIRECTORY):
    app.mount("/favicons", StaticFiles(directory=FRONTEND_FAVICONS_DIRECTORY), "favicons")


@app.get("/{rest_of_path:path}", include_in_schema=False)
async def react_app(req: Request, rest_of_path: str) -> Response:  # pylint: disable=unused-argument
    if rest_of_path == "docs":
        return RedirectResponse("/docs/")
    return templates.TemplateResponse("index.html", {"request": req})
