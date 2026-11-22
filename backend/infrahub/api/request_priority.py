from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.database.routing import bind_execution_priority
from infrahub.workflows.constants import WorkflowPriority

from .admission.priority import parse_priority, read_priority_header

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


class RequestPriorityMiddleware:
    """Pure-ASGI middleware that makes the priority header of an HTTP request the priority its database sessions serve.

    A request without a valid header serves the medium priority, as it does in the admission layer. Non-``http``
    scopes pass through and serve no priority.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        parsed = parse_priority(read_priority_header(scope))
        with bind_execution_priority(WorkflowPriority(parsed.priority.label)):
            await self.app(scope, receive, send)
