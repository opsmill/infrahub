from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi.responses import JSONResponse
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from ..exception_handlers import GRAPHQL_PATH_PREFIX
from . import metrics
from .controller import Admitted
from .priority import parse_priority

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

    from .controller import AdmissionController

EXCLUDED_PATHS: tuple[str, ...] = (
    "/health",
    "/metrics",
    "/assets",
    "/favicons",
    "/docs",
    "/api/schema",
)

_PRIORITY_HEADER = b"x-priority"

_SHED_MESSAGE = "Server is shedding load; retry later."


class AdmissionMiddleware:
    """Pure-ASGI outermost gate that sheds load by priority before any handler work.

    Non-``http`` scopes, the excluded liveness/scrape/static paths, and every request
    while the layer is disabled pass straight through. Otherwise the ``X-Priority`` header
    is classified and handed to the admission controller: an admitted request runs the
    downstream app inside its slot and always releases the slot afterwards, while a shed
    request is answered with a ``429`` error envelope carrying ``Retry-After`` and never
    reaches the app.

    The controller and the enabled flag are injected so the gate is exercisable without
    global settings or a live server.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        controller: AdmissionController,
        enabled: bool,
        excluded_paths: tuple[str, ...] = EXCLUDED_PATHS,
    ) -> None:
        self.app = app
        self._controller = controller
        self._enabled = enabled
        self._excluded_paths = excluded_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._enabled:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if any(path.startswith(excluded) for excluded in self._excluded_paths):
            await self.app(scope, receive, send)
            return

        parsed = parse_priority(_read_priority_header(scope))
        if not parsed.was_explicit:
            metrics.MISSING_PRIORITY_TOTAL.inc()

        decision = await self._controller.admit(priority=parsed.priority)
        if isinstance(decision, Admitted):
            try:
                await self.app(scope, receive, send)
            finally:
                decision.acquisition.release()
            return

        # Short-circuit: the shed response is written directly, so the downstream app and
        # every handler dependency (auth, routing, DB query) never runs.
        response = _build_shed_response(path=path, retry_after=decision.retry_after)
        await response(scope, receive, send)


def _read_priority_header(scope: Scope) -> str | None:
    for name, value in scope["headers"]:
        if name == _PRIORITY_HEADER:
            return value.decode("latin-1")
    return None


def _build_shed_response(*, path: str, retry_after: int) -> JSONResponse:
    """Build the ``429`` shed response with a ``Retry-After`` header.

    The body is the Infrahub error envelope, selected REST vs GraphQL by request path.
    Both surfaces use the integer-code envelope: a shed is a transport-level outcome with
    no exception to map through the error catalogue, so the GraphQL catalogue envelope
    (string code, ``http_status``, typed ``data``) does not apply.
    """
    if path.startswith(GRAPHQL_PATH_PREFIX):
        content = _graphql_shed_envelope()
    else:
        content = _rest_shed_envelope()
    return JSONResponse(
        status_code=HTTP_429_TOO_MANY_REQUESTS,
        content=content,
        headers={"Retry-After": str(retry_after)},
    )


def _rest_shed_envelope() -> dict[str, Any]:
    return {
        "data": None,
        "errors": [{"message": _SHED_MESSAGE, "extensions": {"code": HTTP_429_TOO_MANY_REQUESTS}}],
    }


def _graphql_shed_envelope() -> dict[str, Any]:
    return {
        "data": None,
        "errors": [{"message": _SHED_MESSAGE, "extensions": {"code": HTTP_429_TOO_MANY_REQUESTS}}],
    }
