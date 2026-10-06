"""Running a git command that has to end within a deadline, together with every process it started."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess  # noqa: S404
from typing import TYPE_CHECKING

from git import Git
from git.exc import GitCommandError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def run_git_with_deadline(
    args: Sequence[str],
    *,
    working_directory: str | os.PathLike[str],
    environment: Mapping[str, str],
    timeout_seconds: float,
    stop_grace_seconds: float,
) -> None:
    """Run git with ``args``, stopping it and every process it started once ``timeout_seconds`` pass.

    git runs in a process group of its own. On the deadline the whole group is sent ``SIGTERM``, which
    git handles by removing the lock files and temporary files it holds, and the group is killed
    outright if it is still running ``stop_grace_seconds`` later. The environment is the worker's,
    with the C locale git's error messages are matched in and ``environment`` on top.

    Raises:
        GitCommandError: When git exits with a non-zero status, or did not finish before the deadline.

    """
    command = [Git.GIT_PYTHON_GIT_EXECUTABLE or "git", *args]
    process_environment = {**os.environ, "LANGUAGE": "C", "LC_ALL": "C", **environment}
    with subprocess.Popen(  # noqa: S603
        command,
        cwd=working_directory,
        env=process_environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,
    ) as process:
        try:
            _, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            stderr = _stop_process_group(process, grace_seconds=stop_grace_seconds)
            raise GitCommandError(
                command,
                process.returncode,
                stderr=f"git did not finish within {timeout_seconds:g}s and was stopped. {_decode(stderr)}".strip(),
            ) from None

    if process.returncode != 0:
        raise GitCommandError(command, process.returncode, stderr=_decode(stderr))


def _stop_process_group(process: subprocess.Popen[bytes], *, grace_seconds: float) -> bytes:
    """Stop git's process group, and return whatever git wrote to stderr before it ended."""
    _signal_process_group(process, signal.SIGTERM)
    try:
        _, stderr = process.communicate(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        _signal_process_group(process, signal.SIGKILL)
        try:
            _, stderr = process.communicate(timeout=grace_seconds)
        except subprocess.TimeoutExpired as exc:
            # A process that left the group can still hold the pipe open, so stop waiting for its output.
            process.wait()
            return exc.stderr or b""
    return stderr or b""


def _signal_process_group(process: subprocess.Popen[bytes], signal_number: int) -> None:
    # The group has no members left once every process in it exited, which is the outcome being asked for.
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal_number)


def _decode(stderr: bytes | None) -> str:
    return (stderr or b"").decode(errors="replace")
