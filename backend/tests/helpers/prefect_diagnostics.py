"""Report on an ephemeral Prefect test server that stopped answering.

When a Prefect test server wedges, the test process only ever sees the symptom: read timeouts,
websocket handshakes that never complete, and pytest timeouts on every fixture that needs the
task manager. Nothing in the CI log describes the server itself, so the same failure keeps
coming back undiagnosed.

Whoever launches such a server registers it here along with the file its output is redirected
to. Code that gives up on a Prefect call then asks every registered server for the stacks of all
its threads (SIGUSR1) and prints the tail of its log. pytest captures that as part of the failing
test, so the report travels with the failure into the CI log.

Nothing here raises: it runs on a path that is already failing, and a broken diagnostic must not
replace the original error.
"""

from __future__ import annotations

import signal
import sys
import time
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TextIO

if TYPE_CHECKING:
    import subprocess  # noqa: S404 - the server being reported on is a subprocess
    from pathlib import Path

# How much of the server log to show. Enough to hold the stack dump of every thread plus
# whatever the server complained about before it went quiet.
LOG_TAIL_LINES = 300

# Upper bound on how long the server is given to write its stack dump. faulthandler writes
# synchronously from the signal handler, so this only covers signal delivery.
STACK_DUMP_TIMEOUT_SECONDS = 2.0
STACK_DUMP_POLL_SECONDS = 0.05


@dataclass(frozen=True)
class PrefectTestServerProcess:
    """An ephemeral Prefect test server subprocess and the file its output is redirected to."""

    port: int
    process: subprocess.Popen[Any]
    log_path: Path


_servers: list[PrefectTestServerProcess] = []


def register_prefect_test_server(port: int, process: subprocess.Popen[Any], log_path: Path) -> None:
    """Record a Prefect test server subprocess so its state can be reported on later.

    Register every launch attempt: the ephemeral server is restarted on a port collision, and a
    registration whose process has died reports itself as such instead of being silently skipped.
    """
    _servers.append(PrefectTestServerProcess(port=port, process=process, log_path=log_path))


def clear_prefect_test_servers() -> None:
    _servers.clear()


def dump_prefect_test_server_diagnostics(reason: str, stream: TextIO | None = None) -> None:
    """Print what every registered Prefect test server is doing, prefixed by ``reason``.

    A no-op when no server was registered, which is every suite that does not run one.
    """
    if not _servers:
        return

    out = stream if stream is not None else sys.stderr
    try:
        print(f"\n{'=' * 30} Prefect test server diagnostics {'=' * 30}", file=out)
        print(reason, file=out)
        for server in _servers:
            _dump_server(server, out=out)
        print("=" * 93, file=out)
<<<<<<< HEAD
    except Exception:  # noqa: BLE001 - a broken diagnostic must not replace the failure it reports on
||||||| 1a4dc249d
=======
    except Exception:
>>>>>>> origin/stable
        print("Failed to report on the Prefect test server:", file=out)
        traceback.print_exc(file=out)


def _dump_server(server: PrefectTestServerProcess, out: TextIO) -> None:
    print(f"\n--- Prefect test server on port {server.port} (pid {server.process.pid}) ---", file=out)
    size_before = _log_size(server)
    if _request_stack_dump(server, out=out):
        _wait_for_stack_dump(server, size_before=size_before)
    _print_log_tail(server, out=out)


def _request_stack_dump(server: PrefectTestServerProcess, out: TextIO) -> bool:
    """Ask the server to write the stacks of all its threads to its log. True if it was alive."""
    exit_code = server.process.poll()
    if exit_code is not None:
        print(f"process exited with code {exit_code} before it could be asked for its stacks", file=out)
        return False

    try:
        server.process.send_signal(signal.SIGUSR1)
    except OSError as exc:
        print(f"could not signal the process for a stack dump: {exc}", file=out)
        return False
    return True


def _wait_for_stack_dump(server: PrefectTestServerProcess, size_before: int) -> None:
    deadline = time.monotonic() + STACK_DUMP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if _log_size(server) > size_before:
            return
        time.sleep(STACK_DUMP_POLL_SECONDS)


def _log_size(server: PrefectTestServerProcess) -> int:
    try:
        return server.log_path.stat().st_size
    except OSError:
        return 0


def _print_log_tail(server: PrefectTestServerProcess, out: TextIO) -> None:
    try:
        lines = server.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        print(f"could not read {server.log_path}: {exc}", file=out)
        return

    if not lines:
        print(f"{server.log_path} is empty: the server neither logged nor answered the stack dump", file=out)
        return

    dropped = max(len(lines) - LOG_TAIL_LINES, 0)
    if dropped:
        print(f"... {dropped} earlier lines in {server.log_path}", file=out)
    for line in lines[-LOG_TAIL_LINES:]:
        print(line, file=out)
