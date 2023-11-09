import os
from typing import Any

from fastapi.logger import logger
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

import infrahub.config as config


class InfrahubCORSMiddleware(CORSMiddleware):
    def __init__(self, app: ASGIApp, *args: Any, **kwargs: Any):
        if not config.SETTINGS:
            config_file_name = os.environ.get("INFRAHUB_CONFIG", "infrahub.toml")
            config_file_path = os.path.abspath(config_file_name)
            logger.info(f"Loading the configuration from {config_file_path}")
            config.load_and_exit(config_file_path)

        kwargs["allow_origins"] = config.SETTINGS.api.cors_allow_origins
        kwargs["allow_credentials"] = config.SETTINGS.api.cors_allow_credentials
        kwargs["allow_methods"] = config.SETTINGS.api.cors_allow_methods
        kwargs["allow_headers"] = config.SETTINGS.api.cors_allow_headers

        super().__init__(app, *args, **kwargs)
