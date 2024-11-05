from typing import Any

from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from infrahub import config


class InfrahubCORSMiddleware(CORSMiddleware):
    def __init__(self, app: ASGIApp, *args: Any, **kwargs: Any) -> None:
        config.SETTINGS.initialize_and_exit()
        kwargs["allow_origins"] = config.SETTINGS.api.cors_allow_origins
        kwargs["allow_credentials"] = config.SETTINGS.api.cors_allow_credentials
        kwargs["allow_methods"] = config.SETTINGS.api.cors_allow_methods
        kwargs["allow_headers"] = config.SETTINGS.api.cors_allow_headers

        super().__init__(app, *args, **kwargs)
