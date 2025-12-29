from typing import Any

from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from infrahub import config


class InfrahubCORSMiddleware(CORSMiddleware):
    def __init__(self, app: ASGIApp, *args: Any, **kwargs: Any) -> None:
        config.SETTINGS.initialize_and_exit()
        kwargs["allow_origins"] = config.SETTINGS.api.cors_allow_origins
        kwargs["allow_credentials"] = config.SETTINGS.api.cors_allow_credentials
        kwargs["allow_methods"] = config.SETTINGS.api.cors_allow_methods
        kwargs["allow_headers"] = config.SETTINGS.api.cors_allow_headers

        super().__init__(app, *args, **kwargs)


class ConditionalGZipMiddleware(GZipMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        minimum_size: int = 500,
        compresslevel: int = 9,
        include_paths: tuple[str, ...] = (),
    ) -> None:
        super().__init__(app, minimum_size=minimum_size, compresslevel=compresslevel)
        self.include_paths = include_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:  # type: ignore[override]
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if any(path.startswith(include) for include in self.include_paths):
            await super().__call__(scope, receive, send)
        else:
            await self.app(scope, receive, send)
