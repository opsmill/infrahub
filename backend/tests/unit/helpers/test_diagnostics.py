"""Tests for the diagnostic helper in tests.helpers.diagnostics."""

import asyncio
import contextlib
import io
import socket
from types import SimpleNamespace
from typing import Callable, Generator

import pytest
import redis.asyncio as redis
from redis.asyncio.connection import Connection, ConnectionPool

from tests.helpers import diagnostics
from tests.helpers.diagnostics import dump_event_loop_closed_diagnostic


@pytest.fixture
def captured_stderr(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    buffer = io.StringIO()
    monkeypatch.setattr(diagnostics, "stderr", buffer)
    return buffer


@pytest.fixture
def install_service_pool(monkeypatch: pytest.MonkeyPatch) -> Callable[[ConnectionPool | None], None]:
    """Install a service on app.state whose ._cache.connection.connection_pool resolves
    to the given pool. Uses a real redis.Redis for the .connection layer
    so only the outer service/cache pair is a SimpleNamespace."""

    def _install(pool: ConnectionPool | None) -> None:
        if pool is None:
            monkeypatch.setattr(diagnostics.app.state, "service", None, raising=False)
            return
        service = SimpleNamespace(_cache=SimpleNamespace(connection=redis.Redis(connection_pool=pool)))
        monkeypatch.setattr(diagnostics.app.state, "service", service, raising=False)

    return _install


_WriterWithLoop = tuple[asyncio.StreamWriter, asyncio.AbstractEventLoop]


@pytest.fixture
def closed_loop_writer() -> Generator[_WriterWithLoop, None, None]:
    """Real StreamWriter whose event loop has been closed — mirrors the production
    failure mode. GC of the orphaned writer emits ResourceWarning; callers should
    use @pytest.mark.filterwarnings("ignore::ResourceWarning")."""
    loop = asyncio.new_event_loop()
    sock_a, sock_b = socket.socketpair()
    try:
        _reader, writer = loop.run_until_complete(asyncio.open_connection(sock=sock_a))
        loop.close()
        yield writer, loop
    finally:
        sock_b.close()


@pytest.fixture
def open_loop_writer() -> Generator[_WriterWithLoop, None, None]:
    """Real StreamWriter on a running event loop; cleanly closed in teardown."""
    loop = asyncio.new_event_loop()
    sock_a, sock_b = socket.socketpair()
    writer = None
    try:
        _reader, writer = loop.run_until_complete(asyncio.open_connection(sock=sock_a))
        yield writer, loop
    finally:
        if writer:
            writer.close()
            with contextlib.suppress(Exception):
                loop.run_until_complete(writer.wait_closed())
        loop.close()
        sock_b.close()


def _caught_runtime_error(message: str = "Event loop is closed") -> RuntimeError:
    try:
        raise RuntimeError(message)
    except RuntimeError as exc:
        return exc


def test_dump_header_node_and_traceback_with_no_service(
    install_service_pool: Callable[[ConnectionPool | None], None], captured_stderr: io.StringIO
) -> None:
    install_service_pool(None)

    dump_event_loop_closed_diagnostic("tests/foo.py::test_bar", _caught_runtime_error())

    output = captured_stderr.getvalue()
    assert "Event loop closed during test_client teardown" in output
    assert "  node: tests/foo.py::test_bar" in output
    assert "  traceback:" in output
    assert "RuntimeError: Event loop is closed" in output
    assert "  redis pool: <none>" in output


@pytest.mark.filterwarnings("ignore::ResourceWarning")
def test_dump_redis_pool_details(
    install_service_pool: Callable[[ConnectionPool | None], None],
    captured_stderr: io.StringIO,
    closed_loop_writer: _WriterWithLoop,
    open_loop_writer: _WriterWithLoop,
) -> None:
    closed_writer, closed_loop = closed_loop_writer
    open_writer, open_loop = open_loop_writer
    conn_available = Connection()
    conn_available._writer = closed_writer
    conn_in_use = Connection()
    conn_in_use._writer = open_writer

    pool = ConnectionPool()
    pool._available_connections.append(conn_available)
    pool._in_use_connections.add(conn_in_use)

    install_service_pool(pool)

    dump_event_loop_closed_diagnostic("nid", _caught_runtime_error())

    output = captured_stderr.getvalue()
    assert f"  redis pool: {pool!r}" in output
    assert "    _available_connections (n=1):" in output
    assert "    _in_use_connections (n=1):" in output
    assert (
        f"      conn={id(conn_available)} writer={id(closed_writer)} loop={id(closed_loop)} loop_closed=True"
    ) in output
    assert (f"      conn={id(conn_in_use)} writer={id(open_writer)} loop={id(open_loop)} loop_closed=False") in output


def test_dump_redis_pool_with_empty_connection_buckets(
    install_service_pool: Callable[[ConnectionPool | None], None], captured_stderr: io.StringIO
) -> None:
    install_service_pool(ConnectionPool())

    dump_event_loop_closed_diagnostic("nid", _caught_runtime_error())

    output = captured_stderr.getvalue()
    assert "    _available_connections (n=0):" in output
    assert "    _in_use_connections (n=0):" in output


def test_dump_handles_connection_without_writer(
    install_service_pool: Callable[[ConnectionPool | None], None], captured_stderr: io.StringIO
) -> None:
    pool = ConnectionPool()
    conn = Connection()
    pool._available_connections.append(conn)
    install_service_pool(pool)

    dump_event_loop_closed_diagnostic("nid", _caught_runtime_error())

    assert f"      conn={id(conn)} writer=None loop=None loop_closed=n/a" in captured_stderr.getvalue()


def test_dump_catches_exception_in_diagnostic_section(
    monkeypatch: pytest.MonkeyPatch, captured_stderr: io.StringIO
) -> None:
    class BoomService:
        @property
        def _cache(self) -> object:
            raise RuntimeError("boom")

    monkeypatch.setattr(diagnostics.app.state, "service", BoomService(), raising=False)

    dump_event_loop_closed_diagnostic("nid", _caught_runtime_error())

    output = captured_stderr.getvalue()
    assert "Event loop closed during test_client teardown" in output
    assert "  (diagnostic dump failed: RuntimeError('boom')" in output


def test_dump_surfaces_attribute_error_when_pool_internals_change(
    monkeypatch: pytest.MonkeyPatch, captured_stderr: io.StringIO
) -> None:
    class RenamedPool:
        @property
        def _available_connections(self) -> list:
            raise AttributeError("'ConnectionPool' object has no attribute '_available_connections'")

        def __repr__(self) -> str:
            return "<redis.asyncio.connection.ConnectionPool(...)>"

    pool = RenamedPool()
    service = SimpleNamespace(_cache=SimpleNamespace(connection=SimpleNamespace(connection_pool=pool)))
    monkeypatch.setattr(diagnostics.app.state, "service", service, raising=False)

    dump_event_loop_closed_diagnostic("nid", _caught_runtime_error())

    output = captured_stderr.getvalue()
    assert "  redis pool: <redis.asyncio.connection.ConnectionPool(...)>" in output
    assert "  (diagnostic dump failed: AttributeError(" in output
    assert "_available_connections (n=0):" not in output
