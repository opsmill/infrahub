from __future__ import annotations

import asyncio
import socket
import subprocess  # noqa: S404
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest
from git import Repo
from git.exc import GitCommandError

from infrahub.git.bounded_command import run_git_with_deadline

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

TIMEOUT_SECONDS = 1.0
STOP_GRACE_SECONDS = 1.0
WAIT_SECONDS = 30
"""Bounds each test's wait, far above the deadline, so a regression fails instead of hanging the suite."""


@contextmanager
def silent_remote() -> Iterator[int]:
    """Accept connections on a loopback port and never answer, the way a hung remote host behaves."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    held: list[socket.socket] = []
    stopped = threading.Event()

    def accept() -> None:
        while not stopped.is_set():
            try:
                connection, _ = server.accept()
            except OSError:
                return
            held.append(connection)

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    try:
        yield server.getsockname()[1]
    finally:
        stopped.set()
        server.close()
        for connection in held:
            connection.close()


def running_commands_containing(marker: str) -> list[str]:
    listing = subprocess.run(["ps", "-A", "-o", "command="], capture_output=True, text=True, check=True).stdout  # noqa: S607
    return [line for line in listing.splitlines() if marker in line and "ps -A" not in line]


def build_clone(tmp_path: Path, origin_url: str) -> Repo:
    repo = Repo.init(tmp_path / "clone")
    repo.create_remote("origin", origin_url)
    return repo


def build_origin(tmp_path: Path) -> Repo:
    origin = Repo.init(tmp_path / "origin")
    with origin.config_writer() as config:
        config.set_value("user", "email", "test@example.com")
        config.set_value("user", "name", "Test")
    (tmp_path / "origin" / "file.txt").write_text("content", encoding="utf-8")
    origin.index.add(["file.txt"])
    origin.index.commit("initial")
    origin.create_tag("release")
    return origin


async def fetch(repo: Repo, *, timeout_seconds: float = TIMEOUT_SECONDS) -> None:
    await asyncio.wait_for(
        asyncio.to_thread(
            run_git_with_deadline,
            ["fetch", "--prune", "--tags", "--prune-tags", "--force", "origin"],
            working_directory=repo.working_dir,
            environment={},
            timeout_seconds=timeout_seconds,
            stop_grace_seconds=STOP_GRACE_SECONDS,
        ),
        timeout=WAIT_SECONDS,
    )


@pytest.mark.parametrize("scheme", ["git", "http"])
async def test_a_fetch_from_a_remote_that_never_answers_is_stopped_with_every_process_it_started(
    tmp_path: Path, scheme: str
) -> None:
    """An http remote is fetched by a helper process git starts, which has to be stopped as well."""
    with silent_remote() as port:
        url = f"{scheme}://127.0.0.1:{port}/stalled.git"
        repo = build_clone(tmp_path, origin_url=url)

        with pytest.raises(GitCommandError, match=r"git did not finish within 1s and was stopped\."):
            await fetch(repo)

        assert running_commands_containing(f"127.0.0.1:{port}") == []


async def test_a_process_that_ignores_the_stop_signal_is_killed_once_the_grace_period_ends(tmp_path: Path) -> None:
    """A process that ignores SIGTERM and keeps git's stderr open would otherwise keep the call waiting."""
    marker = "37.123"
    repo = build_clone(tmp_path, origin_url=str(tmp_path / "unused"))

    with pytest.raises(GitCommandError, match=r"git did not finish within 1s and was stopped\."):
        await asyncio.wait_for(
            asyncio.to_thread(
                run_git_with_deadline,
                ["-c", f"alias.stall=!trap '' TERM; sleep {marker}", "stall"],
                working_directory=repo.working_dir,
                environment={},
                timeout_seconds=TIMEOUT_SECONDS,
                stop_grace_seconds=STOP_GRACE_SECONDS,
            ),
            timeout=WAIT_SECONDS,
        )

    assert running_commands_containing(f"sleep {marker}") == []


async def test_a_failing_fetch_reports_git_s_english_error_and_status(tmp_path: Path) -> None:
    """Git errors are classified by their English wording, so the locale must not translate them."""
    repo = build_clone(tmp_path, origin_url=str(tmp_path / "missing"))

    with pytest.raises(GitCommandError, match=r"does not appear to be a git repository") as raised:
        await fetch(repo)

    assert raised.value.status == 128


async def test_a_repository_can_be_fetched_into_after_a_stopped_fetch(tmp_path: Path) -> None:
    origin = build_origin(tmp_path)
    with silent_remote() as port:
        repo = build_clone(tmp_path, origin_url=f"git://127.0.0.1:{port}/stalled.git")
        with pytest.raises(GitCommandError, match=r"git did not finish within 1s and was stopped\."):
            await fetch(repo)

    repo.remotes.origin.set_url(str(tmp_path / "origin"))
    await fetch(repo)

    assert str(repo.commit(f"origin/{origin.active_branch.name}")) == str(origin.head.commit)
    assert str(repo.commit("release")) == str(origin.head.commit)
