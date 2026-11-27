from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.api.request_priority import RequestPriorityMiddleware
from infrahub.execution_priority import get_execution_priority
from infrahub.workflows.constants import WorkflowPriority

if TYPE_CHECKING:
    from starlette.types import Message, Receive, Scope, Send


async def receive() -> Message:
    return {"type": "http.request"}


async def send(message: Message) -> None:
    return None


class PriorityRecorder:
    """Inner ASGI app that records the execution priority each call serves."""

    def __init__(self) -> None:
        self.priorities: list[WorkflowPriority | None] = []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.priorities.append(get_execution_priority())


@dataclass
class HeaderCase:
    name: str
    headers: list[tuple[bytes, bytes]]
    expected: WorkflowPriority


HEADER_CASES = [
    HeaderCase(name="high", headers=[(b"x-priority", b"high")], expected=WorkflowPriority.HIGH),
    HeaderCase(name="low", headers=[(b"x-priority", b"low")], expected=WorkflowPriority.LOW),
    HeaderCase(name="missing_header", headers=[], expected=WorkflowPriority.MEDIUM),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in HEADER_CASES])
async def test_http_request_serves_the_priority_of_its_header(case: HeaderCase) -> None:
    recorder = PriorityRecorder()

    await RequestPriorityMiddleware(recorder)({"type": "http", "headers": case.headers}, receive, send)

    assert recorder.priorities == [case.expected]
    assert get_execution_priority() is None


async def test_websocket_serves_no_priority() -> None:
    recorder = PriorityRecorder()

    await RequestPriorityMiddleware(recorder)(
        {"type": "websocket", "headers": [(b"x-priority", b"low")]}, receive, send
    )

    assert recorder.priorities == [None]
