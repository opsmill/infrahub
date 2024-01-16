import logging
import os
from typing import TYPE_CHECKING, Any, Dict, List

import structlog
from pydantic import TypeAdapter

if TYPE_CHECKING:
    from structlog.types import Processor

INFRAHUB_PRODUCTION = TypeAdapter(bool).validate_python(os.environ.get("INFRAHUB_PRODUCTION", True))
INFRAHUB_LOG_LEVEL = os.environ.get("INFRAHUB_LOG_LEVEL", "INFO")


def clear_log_context() -> None:
    structlog.contextvars.clear_contextvars()


def get_logger(name: str = "infrahub") -> structlog.stdlib.BoundLogger:
    return structlog.stdlib.get_logger(name)


def get_log_data() -> Dict[str, Any]:
    return structlog.contextvars.get_contextvars()


def set_log_data(key: str, value: Any) -> None:
    structlog.contextvars.bind_contextvars(**{key: value})


def configure_logging(production: bool = True, log_level: str = "INFO") -> None:
    shared_processors: List[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
    ]

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
        log_renderer = structlog.dev.ConsoleRenderer()

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, log_renderer],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)


configure_logging(production=INFRAHUB_PRODUCTION, log_level=INFRAHUB_LOG_LEVEL)
