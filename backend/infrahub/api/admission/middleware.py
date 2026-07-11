from __future__ import annotations

import json
from typing import TYPE_CHECKING

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

_SHED_BODY = json.dumps(
    {
        "data": None,
        "errors": [{"message": "Server is shedding load; retry later.", "extensions": {"code": 429}}],
    }
).encode("utf-8")


class AdmissionMiddleware:
    """Pure-ASGI outermost gate that sheds load by priority before any handler work.

    Non-``http`` scopes, the excluded liveness/scrape/static paths, and every request
    while the layer is disabled pass straight through. Otherwise the ``X-Priority`` header
    is classified and handed to the admission controller: an admitted request runs the
    downstream app inside its slot and always releases the slot afterwards, while a shed
    request is answered with a bare ``429`` carrying ``Retry-After`` and never reaches the
    app.

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

        await _send_shed_response(send=send, retry_after=decision.retry_after)


def _read_priority_header(scope: Scope) -> str | None:
    for name, value in scope["headers"]:
        if name == _PRIORITY_HEADER:
            return value.decode("latin-1")
    return None


async def _send_shed_response(*, send: Send, retry_after: int) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 429,
            "headers": [
                (b"content-type", b"application/json"),
                (b"retry-after", str(retry_after).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": _SHED_BODY})
