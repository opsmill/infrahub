import logging
import logging.config
from typing import Any


class DefaultFilter(logging.Filter):
    """Default Filter"""

    def filter(self, _: logging.LogRecord) -> bool:
        """Log everything"""
        return True


class InfrahubLog:
    """Infrahub Logging"""

    logger: logging.Logger

    def __init__(self):
        self.logger_name = "infrahub"
        self.handler = "console"
        self.level = "DEBUG"
        self._apply_configuration()
        self.logger = logging.getLogger(self.logger_name)
        self.info = self.logger.info
        self.debug = self.logger.debug
        self.warning = self.logger.warning
        self.error = self.logger.error
        self.critical = self.logger.critical

    def _apply_configuration(self) -> None:
        log_config: dict[str, Any] = {
            "version": 1,
            "formatters": {
                "simple": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"},
                "rich_formatter": {"format": "%(name)s | %(message)s", "datefmt": "[%X]"},
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "DEBUG",
                    "formatter": "simple",
                    "filters": ["default"],
                    "stream": "ext://sys.stdout",
                },
                "rich": {
                    "class": "rich.logging.RichHandler",
                    "level": "DEBUG",
                    "formatter": "rich_formatter",
                    "filters": ["default"],
                },
            },
            "loggers": {
                self.logger_name: {
                    "level": self.level,
                    "handlers": [
                        self.handler,
                    ],
                    "propagate": False,
                },
                "neo4j": {
                    "level": "ERROR",
                    "handlers": [self.handler],
                    "propagate": False,
                },
                "httpx": {
                    "level": "ERROR",
                    "handlers": [self.handler],
                    "propagate": False,
                },
                "httpcore": {
                    "level": "ERROR",
                    "handlers": [self.handler],
                    "propagate": False,
                },
                "aio_pika": {
                    "level": "ERROR",
                    "handlers": [self.handler],
                    "propagate": False,
                },
                "aiormq": {
                    "level": "ERROR",
                    "handlers": [self.handler],
                    "propagate": False,
                },
                "git": {
                    "level": "ERROR",
                    "handlers": [self.handler],
                    "propagate": False,
                },
            },
            "filters": {
                "default": {
                    "()": DefaultFilter,
                },
            },
            "root": {"level": "INFO", "handlers": ["console"]},
        }
        logging.config.dictConfig(log_config)
        self.logger = logging.getLogger(self.logger_name)
        self.info = self.logger.info
        self.debug = self.logger.debug
        self.warning = self.logger.warning
        self.error = self.logger.error
        self.critical = self.logger.critical

    def set_name(self, name: str) -> None:
        self.logger_name = name
        self._apply_configuration()

    def set_handler(self, name: str) -> None:
        self.handler = name
        self._apply_configuration()


log = InfrahubLog()
