from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import Any

import httpx
from prefect.client.orchestration import PrefectClient
from rich.console import Console

TASK_MANAGER_API = "http://task-manager:4200/api"
CLEANUP_PATH = "/api/infrahub/task-history/cleanup"


@dataclass(frozen=True)
class RecordedRequest:
    method: str
    path: str
    body: Any = None


def cleanup_job(**fields: Any) -> dict[str, Any]:
    """A cleanup as the task manager serializes it: running, with nothing deleted yet unless the fields say otherwise."""
    return {
        "id": "job-1",
        "state": "running",
        "rewrite": "never",
        "rewritten": False,
        "cutoff": "2026-09-04T00:00:00Z",
        "deleted_runs": 0,
        "current_day": None,
        "size_before": None,
        "size_after": None,
        "not_rewritten": [],
        "error": None,
    } | fields


def started(**fields: Any) -> httpx.Response:
    return httpx.Response(status_code=202, json=cleanup_job(**fields))


def polled(**fields: Any) -> httpx.Response:
    return httpx.Response(status_code=200, json=cleanup_job(**fields))


def route_missing() -> httpx.Response:
    return httpx.Response(status_code=404, json={"detail": "Not Found"})


def running_elsewhere() -> httpx.Response:
    return httpx.Response(status_code=409, json={"detail": "a cleanup is running elsewhere"})


def unknown_cleanup() -> httpx.Response:
    return httpx.Response(status_code=404, json={"detail": "the cleanup is unknown to this task manager"})


class ScriptedTaskManager:
    """Answers the task history cleanup routes with the scripted responses in order, recording each request."""

    def __init__(self, responses: list[httpx.Response]) -> None:
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
        return self._responses.pop(0)


class FakeClock:
    """A monotonic clock that only moves when the code under test sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class RecordedConsole:
    """A console without colours, times or wrapping, whose output reads back as lines."""

    def __init__(self) -> None:
        self._output = io.StringIO()
        self.console = Console(file=self._output, width=500, color_system=None, log_time=False, log_path=False)

    @property
    def lines(self) -> list[str]:
        return [line.rstrip() for line in self._output.getvalue().splitlines()]
