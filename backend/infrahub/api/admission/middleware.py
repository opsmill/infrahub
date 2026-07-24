from __future__ import annotations

from typing import TYPE_CHECKING, Any, assert_never

from fastapi.responses import JSONResponse
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from ..exception_handlers import GRAPHQL_PATH_PREFIX
from . import metrics
from .controller import Admitted, Rejected
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
    "/api/config",
    "/api/schema",
)

_PRIORITY_HEADER = b"x-priority"
_CORS_REQUEST_METHOD_HEADER = b"access-control-request-method"

_SHED_MESSAGE = "Server is shedding load; retry later."


class AdmissionMiddleware:
    """Pure-ASGI outermost gate that sheds load by priority before any handler work.

    Non-``http`` scopes, the excluded liveness/scrape/static paths, and every request
    while the layer is disabled pass straight through. Otherwise the ``X-Priority`` header
    is classified and handed to the admission controller: an admitted request runs the
    downstream app inside its slot and always releases the slot afterwards, while a shed
    request is answered with a ``429`` error envelope carrying ``Retry-After`` and never
    reaches the app.

    The controller and kill-switch are not built here. They are constructed once during
    application startup (the lifespan) and published on ``app.state`` as
    ``admission_controller`` and ``admission_enabled``, which this gate reads per request.
    Building at startup keeps settings resolution and the controller's object graph out of
    the middleware, so the class carries no dependency on global settings and a test can
    exercise the gate by setting those two ``app.state`` attributes on a bare app.
    """

    def __init__(self, app: ASGIApp, *, excluded_paths: tuple[str, ...] = EXCLUDED_PATHS) -> None:
        self.app = app
        self._excluded_paths = excluded_paths

    def _is_excluded(self, path: str) -> bool:
        """Whether a path is an excluded route: an exact match or a slash-delimited descendant.

        Matching the exact path or a ``<excluded>/`` prefix keeps mounted trees (``/assets/...``)
        and their roots excluded without also excluding unrelated paths that merely share a
        leading substring (``/healthcheck`` is not ``/health``).
        """
        return any(path == excluded or path.startswith(f"{excluded}/") for excluded in self._excluded_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if self._is_excluded(path):
            await self.app(scope, receive, send)
            return

        # A CORS preflight carries no X-Priority and would be classified MEDIUM. Shedding it under
        # load would strip the CORS response and break every cross-origin request precisely when the
        # backend is busy, so preflights bypass the gate and reach the downstream CORS middleware.
        if _is_cors_preflight(scope):
            await self.app(scope, receive, send)
            return

        # Excluded paths (liveness/scrape/probe) and preflights bypass above without touching
        # app.state, so probes stay served even if the startup lifespan never published the gate's
        # state. Everything past this point is a gated request, so the state is read now: the
        # kill-switch first, then the controller once a request is actually admitted through it.
        state = scope["app"].state
        if not state.admission_enabled:
            await self.app(scope, receive, send)
            return

        controller: AdmissionController = state.admission_controller
        parsed = parse_priority(_read_priority_header(scope))
        if not parsed.was_explicit:
            metrics.MISSING_PRIORITY_TOTAL.inc()

        decision = await controller.admit(priority=parsed.priority)
        match decision:
            case Admitted():
                try:
                    await self.app(scope, receive, send)
                finally:
                    controller.release(acquisition=decision.acquisition)
            case Rejected():
                # Short-circuit: the shed response is written directly, so the downstream app and
                # every handler dependency (auth, routing, DB query) never runs.
                response = _build_shed_response(path=path, retry_after=decision.retry_after)
                await response(scope, receive, send)
            case _:
                assert_never(decision)


def _is_cors_preflight(scope: Scope) -> bool:
    """Return whether the request is a CORS preflight (OPTIONS advertising a requested method)."""
    if scope.get("method") != "OPTIONS":
        return False
    return any(name == _CORS_REQUEST_METHOD_HEADER for name, _ in scope["headers"])


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
