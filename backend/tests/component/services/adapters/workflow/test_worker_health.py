from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import httpx
import pytest
from prefect.settings import PREFECT_API_URL, temporary_settings

from infrahub.exceptions import DependencyUnhealthyError
from infrahub.health import ErrorCategory, classify_error
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.tls.registry import TlsContextRegistry
from tests.helpers.utils import closed_local_port

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class RecordingStatusServer:
    """Answers every HTTP request with one status code and records the requested paths in order."""

    def __init__(self, status_line: bytes) -> None:
        self.status_line = status_line
        self.paths: list[str] = []

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        request_line = await reader.readline()
        self.paths.append(request_line.split()[1].decode())
        await reader.readuntil(b"\r\n\r\n")
        writer.write(self.status_line + b"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        await writer.drain()
        writer.close()


@asynccontextmanager
async def _task_manager_answering(status_line: bytes) -> AsyncIterator[RecordingStatusServer]:
    recorder = RecordingStatusServer(status_line=status_line)
    server = await asyncio.start_server(recorder.handle, host="127.0.0.1", port=0)
    port = server.sockets[0].getsockname()[1]
    try:
        with temporary_settings(updates={PREFECT_API_URL: f"http://127.0.0.1:{port}/api"}):
            yield recorder
    finally:
        server.close()
        await server.wait_closed()


@pytest.fixture
def workflow() -> WorkflowWorkerExecution:
    return WorkflowWorkerExecution(tls_registry=TlsContextRegistry())


async def test_checks_pass_against_a_running_task_manager(workflow: WorkflowWorkerExecution) -> None:
    await workflow.check_health()
    await workflow.check_database_health()


async def test_database_check_raises_when_the_task_manager_reports_its_database_unavailable(
    workflow: WorkflowWorkerExecution,
) -> None:
    async with _task_manager_answering(b"HTTP/1.1 503 Service Unavailable") as task_manager:
        with pytest.raises(
            DependencyUnhealthyError, match=r"^The task manager answered /ready with HTTP status 503$"
        ) as exc_info:
            await workflow.check_database_health()

    assert task_manager.paths == ["/api/ready"]
    assert classify_error(exc_info.value) == ErrorCategory.UNAVAILABLE


async def test_task_manager_check_requests_the_health_probe(workflow: WorkflowWorkerExecution) -> None:
    async with _task_manager_answering(b"HTTP/1.1 200 OK") as task_manager:
        await workflow.check_health()

    assert task_manager.paths == ["/api/health"]


async def test_checks_raise_when_nothing_listens_at_the_task_manager_address(
    workflow: WorkflowWorkerExecution,
) -> None:
    with temporary_settings(updates={PREFECT_API_URL: f"http://127.0.0.1:{closed_local_port()}/api"}):
        with pytest.raises(httpx.ConnectError, match=r"^All connection attempts failed$") as exc_info:
            await workflow.check_health()

    assert classify_error(exc_info.value) == ErrorCategory.CONNECTION_REFUSED


async def test_checks_raise_when_no_task_manager_address_is_configured(workflow: WorkflowWorkerExecution) -> None:
    with temporary_settings(restore_defaults={PREFECT_API_URL}):
        with pytest.raises(DependencyUnhealthyError, match=r"^The task manager address is not configured$"):
            await workflow.check_health()
