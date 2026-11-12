from __future__ import annotations

from typing import TYPE_CHECKING

from prefect.client.orchestration import get_client
from prefect.settings import PREFECT_CLIENT_CSRF_SUPPORT_ENABLED, temporary_settings

from infrahub.task_manager.client_settings import prefect_client_defaults

if TYPE_CHECKING:
    import httpx

FLOW_RUN_FILTER_PATH = "/api/flow_runs/filter"
CSRF_TOKEN_PATH = "/api/csrf-token"


class RequestRecorder:
    def __init__(self) -> None:
        self.paths: list[str] = []

    async def __call__(self, request: httpx.Request) -> None:
        self.paths.append(request.url.path)


async def read_flow_runs(recorder: RequestRecorder) -> None:
    async with get_client(httpx_settings={"event_hooks": {"request": [recorder]}}, sync_client=False) as client:
        await client.read_flow_runs(limit=1)


async def test_clients_skip_the_csrf_token_request() -> None:
    recorder = RequestRecorder()

    with prefect_client_defaults():
        await read_flow_runs(recorder=recorder)

    assert FLOW_RUN_FILTER_PATH in recorder.paths
    assert CSRF_TOKEN_PATH not in recorder.paths


async def test_explicitly_enabled_csrf_support_is_kept() -> None:
    recorder = RequestRecorder()

    with temporary_settings(updates={PREFECT_CLIENT_CSRF_SUPPORT_ENABLED: True}), prefect_client_defaults():
        await read_flow_runs(recorder=recorder)

    assert FLOW_RUN_FILTER_PATH in recorder.paths
    assert recorder.paths.count(CSRF_TOKEN_PATH) == 1
