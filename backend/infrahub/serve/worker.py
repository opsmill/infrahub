"""Create a Uvicorn worker without the predefined loggers."""

import os
from typing import Any

from uvicorn.workers import UvicornWorker

log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    },
    "handlers": {
        "default": {"formatter": "default", "class": "logging.NullHandler"},
        "access": {"formatter": "access", "class": "logging.NullHandler"},
    },
    "loggers": {
        "uvicorn.error": {"level": "INFO", "handlers": ["default"], "propagate": True},
        "uvicorn.access": {"level": "INFO", "handlers": ["access"], "propagate": False},
    },
}


class InfrahubUvicorn(UvicornWorker):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.config.log_config = log_config
        self.config.configure_logging()
        if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
            for file in os.scandir(os.environ["PROMETHEUS_MULTIPROC_DIR"]):
                os.unlink(file.path)
