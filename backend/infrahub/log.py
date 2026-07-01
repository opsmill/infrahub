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


PREFECT_RUN_LOGGERS = ("prefect.flow_runs", "prefect.task_runs")

_TRACEBACK_SUPPRESSED_TYPES: set[type[BaseException]] = set()


def suppress_traceback_in_logs[TException: type[BaseException]](exc_type: TException) -> TException:
    """Register an exception type so the traceback suppression filter drops its records.

    The registered type represents an expected operational outcome that is already reported as a
    clean reason, so its raised traceback is redundant noise. Registration lives on the class it
    applies to, so the two cannot drift apart, and matching is by exact type identity.
    """
    _TRACEBACK_SUPPRESSED_TYPES.add(exc_type)
    return exc_type


class TracebackSuppressionFilter(logging.Filter):
    """Drop the log record for any exception whose type is in a registered set.

    A logger that reports an exception attaches its traceback to the record. When the exception is an
    expected outcome already reported elsewhere, that traceback is noise, so a record whose exception
    type is registered is dropped before it reaches any handler. The set is read on each record, so a
    type registered after the filter is installed still takes effect.
    """

    def __init__(self, suppressed_types: set[type[BaseException]]) -> None:
        super().__init__()
        self._suppressed_types = suppressed_types

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False to drop the record when its exception is a registered type, True otherwise.

        Per the logging filter contract, returning False discards the whole record, not only its
        traceback. A record carrying no exception, or one whose exception type is not registered, is
        kept; matching is by exact type, so a subclass is not suppressed unless registered in its own
        right.
        """
        exception = record.exc_info[1] if record.exc_info else None
        return type(exception) not in self._suppressed_types


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

    # Prefect ships flow/task run logs to its API; drop tracebacks for failures that
    # are reported as a clean classified reason rather than a crash to debug. Installed after the
    # prefect.main import above so it survives Prefect's logging reset; reads the shared registry that
    # each expected-failure type opts into via suppress_traceback_in_logs.
    traceback_filter = TracebackSuppressionFilter(_TRACEBACK_SUPPRESSED_TYPES)
    for prefect_logger_name in PREFECT_RUN_LOGGERS:
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
