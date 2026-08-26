"""Tests for the Prefect test server report in tests.helpers.prefect_diagnostics."""

import faulthandler
import io
import os
import signal
import subprocess  # noqa: S404
import sys
import time
from collections.abc import Generator
from pathlib import Path

import pytest

from tests.helpers.prefect_diagnostics import (
    LOG_TAIL_LINES,
    clear_prefect_test_servers,
    dump_prefect_test_server_diagnostics,
    register_prefect_test_server,
)
from tests.helpers.prefect_test_server import enable_stack_dump_on_signal

STARTUP_TIMEOUT_SECONDS = 30.0
STARTUP_POLL_SECONDS = 0.05


@pytest.fixture(autouse=True)
def registered_servers() -> Generator[None, None, None]:
    clear_prefect_test_servers()
    yield
    clear_prefect_test_servers()


@pytest.fixture
def idle_server(tmp_path: Path) -> Generator[tuple[subprocess.Popen[bytes], Path], None, None]:
    """A process standing in for a Prefect test server: it answers SIGUSR1 and nothing else."""
    log_path = tmp_path / "server.log"
    script_path = tmp_path / "idle_server.py"
    script_path.write_text(
        "import time\n"
        "from tests.helpers.prefect_test_server import enable_stack_dump_on_signal\n"
        "enable_stack_dump_on_signal()\n"
        "print('server ready', flush=True)\n"
        "time.sleep(600)\n"
    )
    with log_path.open("wb") as log_file:
        process = subprocess.Popen(
            args=[sys.executable, str(script_path)],
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    try:
        _wait_for_startup(process=process, log_path=log_path)
        yield process, log_path
    finally:
        process.kill()
        process.wait()


@pytest.fixture
def exited_server(tmp_path: Path) -> tuple[subprocess.Popen[bytes], Path]:
    """A stand-in server that is already gone by the time anything asks it for its stacks."""
    log_path = tmp_path / "server.log"
    with log_path.open("wb") as log_file:
        process = subprocess.Popen(
            args=[sys.executable, "-c", "raise SystemExit(3)"],
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    process.wait()
    return process, log_path


def _wait_for_startup(process: subprocess.Popen[bytes], log_path: Path) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if "server ready" in log_path.read_text(encoding="utf-8"):
            return
        if process.poll() is not None:
            pytest.fail(f"the stand-in server exited with {process.returncode}: {log_path.read_text(encoding='utf-8')}")
        time.sleep(STARTUP_POLL_SECONDS)
    pytest.fail("the stand-in server never reported itself ready")


def test_sigusr1_dumps_the_stack_of_every_thread(tmp_path: Path) -> None:
    """The report is worthless unless a wedged server answers this signal with its stacks."""
    dump_path = tmp_path / "stacks.log"
    with dump_path.open("w") as dump_file:
        enable_stack_dump_on_signal(file=dump_file)
        try:
            os.kill(os.getpid(), signal.SIGUSR1)
        finally:
            faulthandler.unregister(signal.SIGUSR1)

    dumped = dump_path.read_text()
    assert "Current thread" in dumped
    assert "test_sigusr1_dumps_the_stack_of_every_thread" in dumped


def test_nothing_is_reported_when_no_server_is_registered() -> None:
    out = io.StringIO()

    dump_prefect_test_server_diagnostics("setup timed out", stream=out)

    assert not out.getvalue()


def test_a_registered_server_is_asked_for_its_stacks(idle_server: tuple[subprocess.Popen[bytes], Path]) -> None:
    process, log_path = idle_server
    register_prefect_test_server(port=4242, process=process, log_path=log_path)
    out = io.StringIO()

    dump_prefect_test_server_diagnostics("setup timed out", stream=out)

    reported = out.getvalue()
    assert "setup timed out" in reported
    assert f"Prefect test server on port 4242 (pid {process.pid})" in reported
    assert "Current thread" in reported
    assert f'File "{log_path.parent / "idle_server.py"}", line 5 in <module>' in reported


def test_an_unreadable_log_is_reported_without_raising(
    tmp_path: Path, idle_server: tuple[subprocess.Popen[bytes], Path]
) -> None:
    process, _ = idle_server
    missing_log = tmp_path / "nowhere" / "server.log"
    register_prefect_test_server(port=4242, process=process, log_path=missing_log)
    out = io.StringIO()

    dump_prefect_test_server_diagnostics("setup timed out", stream=out)

    assert f"could not read {missing_log}" in out.getvalue()


def test_a_dead_server_reports_its_exit_code(exited_server: tuple[subprocess.Popen[bytes], Path]) -> None:
    process, log_path = exited_server
    register_prefect_test_server(port=4242, process=process, log_path=log_path)
    out = io.StringIO()

    dump_prefect_test_server_diagnostics("setup timed out", stream=out)

    assert "process exited with code 3 before it could be asked for its stacks" in out.getvalue()


def test_only_the_tail_of_a_long_log_is_reported(exited_server: tuple[subprocess.Popen[bytes], Path]) -> None:
    process, log_path = exited_server
    log_path.write_text("".join(f"line {index}\n" for index in range(LOG_TAIL_LINES + 10)))
    register_prefect_test_server(port=4242, process=process, log_path=log_path)
    out = io.StringIO()

    dump_prefect_test_server_diagnostics("setup timed out", stream=out)

    reported = out.getvalue()
    assert f"... 10 earlier lines in {log_path}" in reported
    assert "line 9\n" not in reported
    assert f"line {LOG_TAIL_LINES + 9}\n" in reported
