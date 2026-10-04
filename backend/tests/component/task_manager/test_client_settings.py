from __future__ import annotations

from typing import TYPE_CHECKING

from prefect.client.orchestration import get_client
from prefect.settings import PREFECT_CLIENT_CSRF_SUPPORT_ENABLED, PREFECT_CLIENT_CUSTOM_HEADERS, temporary_settings

from infrahub.task_manager.client_settings import prefect_client_defaults

if TYPE_CHECKING:
    import httpx

FLOW_RUN_FILTER_PATH = "/api/flow_runs/filter"
CSRF_TOKEN_PATH = "/api/csrf-token"
BLOCK_TYPES_FILTER_PATH = "/api/block_types/filter"


class RequestRecorder:
    def __init__(self) -> None:
        self.paths: list[str] = []
        self.request_headers: list[httpx.Headers] = []
        self.response_encodings: dict[str, str | None] = {}

    async def __call__(self, request: httpx.Request) -> None:
        self.paths.append(request.url.path)
        self.request_headers.append(request.headers)

    async def record_response(self, response: httpx.Response) -> None:
        self.response_encodings[response.request.url.path] = response.headers.get("content-encoding")


async def read_flow_runs(recorder: RequestRecorder) -> None:
    async with get_client(httpx_settings={"event_hooks": {"request": [recorder]}}, sync_client=False) as client:
        await client.read_flow_runs(limit=1)


async def read_block_types(recorder: RequestRecorder) -> None:
    hooks = {"request": [recorder], "response": [recorder.record_response]}
    async with get_client(httpx_settings={"event_hooks": hooks}, sync_client=False) as client:
        assert await client.read_block_types()


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


async def test_clients_receive_uncompressed_responses() -> None:
    recorder = RequestRecorder()

    with prefect_client_defaults():
        await read_block_types(recorder=recorder)

    assert {headers["accept-encoding"] for headers in recorder.request_headers} == {"identity"}
    assert recorder.response_encodings == {BLOCK_TYPES_FILTER_PATH: None}


async def test_explicitly_configured_custom_headers_are_kept() -> None:
    recorder = RequestRecorder()

    with (
        temporary_settings(updates={PREFECT_CLIENT_CUSTOM_HEADERS: {"X-Infrahub-Test": "kept"}}),
        prefect_client_defaults(),
    ):
        await read_flow_runs(recorder=recorder)

    assert {headers.get("x-infrahub-test") for headers in recorder.request_headers} == {"kept"}
    assert {headers["accept-encoding"] for headers in recorder.request_headers} == {"identity"}


async def test_explicitly_configured_accept_encoding_is_kept() -> None:
    recorder = RequestRecorder()

    with (
        temporary_settings(updates={PREFECT_CLIENT_CUSTOM_HEADERS: {"Accept-Encoding": "gzip"}}),
        prefect_client_defaults(),
    ):
        await read_block_types(recorder=recorder)

    assert {headers["accept-encoding"] for headers in recorder.request_headers} == {"gzip"}
    assert recorder.response_encodings == {BLOCK_TYPES_FILTER_PATH: "gzip"}
