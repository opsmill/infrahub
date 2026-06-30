import importlib
import logging
import os
from typing import TYPE_CHECKING, Any

import structlog
from pydantic import TypeAdapter
from structlog.dev import plain_traceback

if TYPE_CHECKING:
    from structlog.types import Processor

INFRAHUB_PRODUCTION = TypeAdapter(bool).validate_python(os.environ.get("INFRAHUB_PRODUCTION", "true"))
INFRAHUB_LOG_LEVEL = os.environ.get("INFRAHUB_LOG_LEVEL", "INFO")


class SuppressMarkedTracebackFilter(logging.Filter):
    """Drop the traceback record Prefect emits for exceptions that opt out of being a stacktrace.

    Prefect's flow/task engine logs every raised exception with ``logger.exception(...)``, attaching
    a traceback. An exception carrying a truthy ``suppress_traceback`` marker represents an expected,
    already-reported operational outcome (its clean reason is logged separately), so the redundant
    traceback record is dropped before it reaches any handler.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        exception = record.exc_info[1] if record.exc_info else None
        return not getattr(exception, "suppress_traceback", False)


def clear_log_context() -> None:
    structlog.contextvars.clear_contextvars()


def get_logger(name: str = "infrahub") -> structlog.stdlib.BoundLogger:
    return structlog.stdlib.get_logger(name)


def get_run_logger(name: str = "infrahub.tasks") -> logging.Logger:
    return logging.getLogger(name)


def get_log_data() -> dict[str, Any]:
    return structlog.contextvars.get_contextvars()


def set_log_data(key: str, value: Any) -> None:
    structlog.contextvars.bind_contextvars(**{key: value})


def configure_logging(production: bool, log_level: str) -> None:
    # Importing prefect.main here triggers prefect.logging.configuration.setup_logging()
    # to be executed, this function wipes out the previous logging configuration and
    # starts from a clean slate. After this has been imported once we can reinject
    # the infrahub logger
    importlib.import_module("prefect.main")

    # Prefect ships flow/task run logs to its API (the Tasks tab); drop tracebacks for failures that
    # are reported as a clean classified reason rather than a crash to debug.
    traceback_filter = SuppressMarkedTracebackFilter()
    for prefect_logger_name in ("prefect.flow_runs", "prefect.task_runs"):
        logging.getLogger(prefect_logger_name).addFilter(traceback_filter)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
    ]
    logging.getLogger("httpx").setLevel(logging.ERROR)

    if production:
        shared_processors.append(structlog.processors.format_exc_info)

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    log_renderer: structlog.types.Processor
    if production:
        log_renderer = structlog.processors.JSONRenderer()
    else:
        log_renderer = structlog.dev.ConsoleRenderer(exception_formatter=plain_traceback)

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, log_renderer],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    for existing_handler in root_logger.handlers:
        if isinstance(existing_handler, logging.StreamHandler):
            root_logger.removeHandler(existing_handler)

    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)


configure_logging(production=INFRAHUB_PRODUCTION, log_level=INFRAHUB_LOG_LEVEL)
