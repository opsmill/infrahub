from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx
from prefect.client.orchestration import PrefectClient

TASK_MANAGER_API = "http://task-manager:4200/api"


@dataclass(frozen=True)
class RecordedRequest:
    method: str
    path: str
    body: Any = None


class ScriptedTaskManager:
    """Answers the task history cleanup routes with the scripted responses in order, recording each request.

    A scripted exception is raised instead of answering, as the transport raises it.
    """

    def __init__(self, responses: list[httpx.Response | httpx.TransportError]) -> None:
        self._responses = list(responses)
        self.requests: list[RecordedRequest] = []

    def client(self) -> PrefectClient:
        return PrefectClient(api=TASK_MANAGER_API, httpx_settings={"transport": httpx.MockTransport(self._handle)})

    def _handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/csrf-token":
            return httpx.Response(status_code=422, json={"detail": "CSRF protection is disabled."})
        body = json.loads(request.content) if request.content else None
        self.requests.append(RecordedRequest(method=request.method, path=request.url.path, body=body))
        if not self._responses:
            raise AssertionError(f"{request.method} {request.url.path} came after the last scripted response")
        response = self._responses.pop(0)
        if isinstance(response, httpx.TransportError):
            raise response
        return response
