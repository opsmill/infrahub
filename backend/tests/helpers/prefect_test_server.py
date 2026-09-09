"""Entry point for the ephemeral Prefect test server subprocess.

This is a plain uvicorn run of the Infrahub Prefect application, wrapped only to make a wedged
server diagnosable.

A Prefect test server that stops answering takes its whole pytest worker down with it: every
later test that needs the task manager blocks until a timeout fires. Such a server is invisible
in a CI log — blocked, it logs nothing at all, and the tests only ever see their own timeouts.

``faulthandler`` gives the test process a way to ask what it is doing. On SIGUSR1 the server
writes the stack of every one of its threads to stderr, which the launcher redirects to a file.
faulthandler writes from inside the signal handler rather than scheduling Python code to run, so
it still answers when the interpreter is too wedged to execute anything else.
"""

from __future__ import annotations

import faulthandler
import signal
import sys
from typing import TextIO


def enable_stack_dump_on_signal(file: TextIO | None = None) -> None:
    """Answer SIGUSR1 with the stack of every thread, written to ``file`` (stderr by default).

    The signal is not chained on: its default action is to kill the process, and a server that
    dies of being asked what it is doing can only be asked once.
    """
    faulthandler.register(signal.SIGUSR1, file=file if file is not None else sys.stderr, all_threads=True, chain=False)


def main() -> None:
    # Fatal errors (a segfault in a native driver, a hard stack overflow) would otherwise leave
    # nothing but an exit code behind.
    faulthandler.enable()
    enable_stack_dump_on_signal()

    from uvicorn.main import main as uvicorn_main  # noqa: PLC0415 - the uvicorn CLI is the process this module wraps

    uvicorn_main()


if __name__ == "__main__":
    main()
