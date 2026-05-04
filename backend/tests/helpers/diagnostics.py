# This file should be deleted once the flakiness is gone
import asyncio
import threading
from sys import stderr
from traceback import format_exception
from typing import Any, cast

from redis.asyncio.connection import Connection, ConnectionPool

from infrahub.server import app

_INSTALLED_MARKER = "__diag_installed__"


def _current_loop_info() -> tuple[int | None, bool | None]:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None, None
    return id(loop), loop.is_closed()


def _conn_creation_info(conn: object) -> tuple[int | None, str | None, str | None]:
    return (
        getattr(conn, "_creation_loop_id", None),
        getattr(conn, "_creation_loop_repr", None),
        getattr(conn, "_creation_thread_name", None),
    )


def dump_event_loop_closed_diagnostic(nodeid: str, exc: BaseException) -> None:
    """Print a Redis pool state summary when a "Event loop is closed" RuntimeError is fired"""

    lines: list[str] = [
        "Event loop closed during test_client teardown — diagnostic dump",
        f"  node: {nodeid}",
        "  traceback:",
    ]
    for line in format_exception(type(exc), exc, exc.__traceback__):
        lines.extend(f"    {sub}" for sub in line.rstrip().splitlines())
    try:
        current_loop_id, current_loop_closed = _current_loop_info()
        lines.append(f"  current loop: id={current_loop_id} closed={current_loop_closed}")
        service = getattr(app.state, "service", None)
        cache = getattr(service, "_cache", None)
        connection = getattr(cache, "connection", None)
        pool = getattr(connection, "connection_pool", None)
        if pool is not None:
            lines.append(f"  redis pool: {pool!r}")
            for attr in ("_available_connections", "_in_use_connections"):
                conns = list(getattr(pool, attr) or [])
                lines.append(f"    {attr} (n={len(conns)}):")
                for conn in conns:
                    try:
                        writer = conn._writer
                        transport = writer._transport
                        loop = transport._loop
                    except AttributeError:
                        writer = transport = loop = None
                    writer_id = id(writer) if writer else None
                    loop_id = id(loop) if loop else None
                    loop_closed = loop.is_closed() if loop is not None else "n/a"
                    creation_loop_id, creation_loop_repr, creation_thread_name = _conn_creation_info(conn)
                    lines.append(
                        f"      conn={id(conn)} writer={writer_id} loop={loop_id} loop_closed={loop_closed}"
                        f" creation_loop={creation_loop_id} creation_loop_repr={creation_loop_repr!r}"
                        f" creation_thread={creation_thread_name!r}"
                    )
        else:
            lines.append("  redis pool: <none>")
    except Exception as diag_exc:
        lines.append(f"  (diagnostic dump failed: {diag_exc!r})")

    print("\n".join(lines), file=stderr, flush=True)


def _dump_pool_loop_divergence(pool: ConnectionPool) -> None:
    """Print a stderr line for every pooled connection whose creation loop differs from the running loop."""
    current_loop_id, _ = _current_loop_info()
    if current_loop_id is None:
        return
    diverged: list[str] = []
    for attr in ("_available_connections", "_in_use_connections"):
        for conn in list(getattr(pool, attr, None) or []):
            creation_loop_id, creation_loop_repr, creation_thread_name = _conn_creation_info(conn)
            if creation_loop_id is None or creation_loop_id == current_loop_id:
                continue
            diverged.append(
                f"  {attr}: conn={id(conn)} creation_loop={creation_loop_id}"
                f" creation_loop_repr={creation_loop_repr!r} creation_thread={creation_thread_name!r}"
                f" current_loop={current_loop_id}"
            )
    if diverged:
        print(
            "\n".join(["Redis pool disconnect loop divergence detected:", *diverged]),
            file=stderr,
            flush=True,
        )


def install_redis_loop_diagnostics() -> None:
    """Monkey-patch redis.asyncio Connection / ConnectionPool to record event-loop identity.

    Stamps `_creation_loop_id`, `_creation_loop_repr`, and `_creation_thread_name` on each Connection
    right after `_connect` succeeds. The fields survive `Connection.disconnect()`'s `finally:`, so the
    post-mortem dump can identify which loop and thread the writer was bound to. Also wraps
    `ConnectionPool.disconnect` to log per-connection loop divergence to stderr *before* the disconnect
    runs — gives a proactive signal even when the underlying disconnect doesn't raise.

    Idempotent: calling it again is a no-op once the marker is set on both patched targets.
    """
    if getattr(Connection._connect, _INSTALLED_MARKER, False) and getattr(
        ConnectionPool.disconnect, _INSTALLED_MARKER, False
    ):
        return

    original_connect = Connection._connect

    async def _instrumented_connect(self: Connection) -> None:
        await original_connect(self)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        cast("Any", self)._creation_loop_id = id(loop)
        cast("Any", self)._creation_loop_repr = repr(loop)
        cast("Any", self)._creation_thread_name = threading.current_thread().name

    original_disconnect = ConnectionPool.disconnect

    async def _instrumented_disconnect(self: ConnectionPool, inuse_connections: bool = True) -> None:
        try:
            _dump_pool_loop_divergence(self)
        except Exception as diag_exc:
            print(f"(redis loop divergence dump failed: {diag_exc!r})", file=stderr, flush=True)
        await original_disconnect(self, inuse_connections=inuse_connections)

    setattr(_instrumented_connect, _INSTALLED_MARKER, True)
    setattr(_instrumented_disconnect, _INSTALLED_MARKER, True)
    cast("Any", Connection)._connect = _instrumented_connect
    cast("Any", ConnectionPool).disconnect = _instrumented_disconnect
