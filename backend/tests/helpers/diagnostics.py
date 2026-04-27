from sys import stderr
from traceback import format_exception

from infrahub.server import app


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
                    lines.append(f"      conn={id(conn)} writer={writer_id} loop={loop_id} loop_closed={loop_closed}")
        else:
            lines.append("  redis pool: <none>")
    except Exception as diag_exc:
        lines.append(f"  (diagnostic dump failed: {diag_exc!r})")

    print("\n".join(lines), file=stderr, flush=True)
