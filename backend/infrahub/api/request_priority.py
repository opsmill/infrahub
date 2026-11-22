from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from infrahub.execution_priority import bind_execution_priority
from infrahub.workflows.constants import WorkflowPriority

from .admission.priority import Priority, parse_request_priority

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

        with bind_execution_priority(_workflow_priority(parse_request_priority(scope).priority)):
            await self.app(scope, receive, send)


def _workflow_priority(priority: Priority) -> WorkflowPriority:
    match priority:
        case Priority.HIGH:
            return WorkflowPriority.HIGH
        case Priority.MEDIUM:
            return WorkflowPriority.MEDIUM
        case Priority.LOW:
            return WorkflowPriority.LOW
        case _:
            assert_never(priority)
