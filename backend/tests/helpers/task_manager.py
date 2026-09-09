"""Run the Prefect task manager setup once per Prefect server.

The task manager setup registers blocks, worker pools, deployments and builtin
triggers against the Prefect server the current settings point at. The inputs are
static and the calls are slow (several seconds of API round-trips), so fixtures
should reuse a single setup per server instead of repeating it for every test or
test class.

The memoization is keyed on the Prefect API URL, not on the process. One test
process talks to more than one Prefect server — an ephemeral in-process one for
the whole session and a container that modules opt into — and each needs its own
registration; a setup done against one server says nothing about the other.

The memo assumes every server it has seen lives for the rest of the process. A
server torn down and recreated at a URL the memo already holds would be skipped,
so callers must only target session-lived servers.

A failure is remembered the same way a success is. An unreachable Prefect test
server does not fail fast — the setup blocks until a timeout fires — so retrying
it for every later test class costs that timeout each time and buries the
original cause under a wall of identical errors.

For that to work the setup has to fail *inside* the coroutine, which is why it
carries its own timeout instead of leaning on the pytest one. pytest-timeout runs
in signal mode, and SIGALRM is raised in whichever frame the main thread happens
to be in — for an async fixture that is the event loop driver, several frames
above the coroutine. Nothing here would see it, nothing would be remembered, and
the next test would start the setup over again. Worse, the abandoned coroutine
stays pending on the session-scoped loop and runs on in between later tests,
hanging tests that never touch Prefect at all.

The setup runs as a task of its own so that giving up on it does not wait for it. Prefect
answers a cancellation by writing a Crashed state to the server, shielded from the
cancellation, and that write goes to the very server that just stopped answering: one
request timeout per attempt, several attempts. Left inline, that bookkeeping ran on past
the pytest timeout, the failure was never remembered, and the next test class paid the
whole timeout again. So the failure is remembered and reported the moment the ceiling is
hit, the task is cancelled, and after a short grace for the bookkeeping to finish it is
left behind.

The ceiling is an event-loop timer, so it cannot fire while the loop is blocked. Prefect's
engine blocks it once per flow start: reading the server's default result storage is a
synchronous HTTP call, with the client's own request timeout and retries. A server that
wedges right there is ended by the pytest timeout alone, and that raises inside the setup
task, whose result then carries the failure to the memo.

A timed-out setup can leave a partially registered server behind. That is no worse
than what the pytest timeout did, and the memo makes sure nothing builds on it.

Tests that intentionally corrupt the shared task manager state must restore it
themselves before yielding back, otherwise later tests will observe the corruption.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import NoReturn

from prefect.settings import get_current_settings

from infrahub.workflows.initialization import setup_task_manager  # noqa: TID251 - the helper wraps the raw setup
from tests.helpers.prefect_diagnostics import dump_prefect_test_server_diagnostics

# Ceiling for one setup attempt. It has to stay under the 300s pytest timeout, so that a wedged
# server is reported from inside the coroutine, and far enough above how long the registration
# takes on a loaded CI runner (tens of seconds, the slowest calls bounded by Prefect's own 60s
# client request timeout) that a slow run is never mistaken for a wedged one. That margin is the
# one worth paying for: giving up too early is remembered, and would condemn a healthy server for
# the rest of the session.
SETUP_TIMEOUT_SECONDS = 180.0

# How long a timed-out setup may spend on Prefect's post-cancellation bookkeeping before it is
# abandoned. Against a healthy but slow server the Crashed state is written in well under a second,
# and the task ends cleanly; against a wedged one the write would take minutes, which is exactly
# the wait this helper exists to avoid.
CRASH_HANDLING_GRACE_SECONDS = 5.0


def _current_prefect_api_url() -> str | None:
    return get_current_settings().api.url


class TaskManagerSetup:
    def __init__(
        self,
        setup: Callable[[], Awaitable[None]] = setup_task_manager,
        server_key: Callable[[], str | None] = _current_prefect_api_url,
        timeout: float = SETUP_TIMEOUT_SECONDS,
        crash_handling_grace: float = CRASH_HANDLING_GRACE_SECONDS,
        report_failure: Callable[[str], None] = dump_prefect_test_server_diagnostics,
    ) -> None:
        self._setup = setup
        self._server_key = server_key
        self._timeout = timeout
        self._crash_handling_grace = crash_handling_grace
        self._report_failure = report_failure
        self._initialized: set[str | None] = set()
        self._failures: dict[str | None, BaseException] = {}

    async def run_once(self) -> None:
        server = self._server_key()

        if server in self._failures:
            raise RuntimeError(f"Prefect task manager setup already failed for {server}") from self._failures[server]

        if server in self._initialized:
            return

        setup = asyncio.ensure_future(self._setup())
        # run_once reads the outcome itself while it is still waiting; once it has moved on, this is
        # what keeps asyncio from logging the outcome as never retrieved.
        setup.add_done_callback(_collect_outcome)
        try:
            done, _ = await asyncio.wait({setup}, timeout=self._timeout)
        except asyncio.CancelledError:
            # Whoever cancelled this call is not waiting for the registration either.
            setup.cancel()
            raise

        if not done:
            await self._give_up(server=server, setup=setup)

        try:
            setup.result()
        # The pytest timeout raises Failed, which derives from BaseException, and that is
        # the failure worth remembering most.
        except BaseException as exc:
            self._remember_failure(server=server, exc=exc)
            raise

        self._initialized.add(server)

    async def _give_up(self, server: str | None, setup: asyncio.Future[None]) -> NoReturn:
        """Remember and report the timeout before the cancellation reaches Prefect, then move on."""
        timeout_error = TimeoutError(f"Prefect task manager setup did not finish within {self._timeout:.0f}s")
        self._remember_failure(server=server, exc=timeout_error)

        setup.cancel()
        await asyncio.wait({setup}, timeout=self._crash_handling_grace)
        ending = _ending_of(setup)
        if ending is not None:
            timeout_error.add_note(f"After the cancellation the setup ended with {ending!r}")

        raise timeout_error

    def _remember_failure(self, server: str | None, exc: BaseException) -> None:
        self._failures[server] = exc
        self._report_failure(f"Prefect task manager setup failed for {server}: {exc!r}")


def _collect_outcome(setup: asyncio.Future[None]) -> None:
    """Mark the setup's outcome as retrieved, so asyncio does not log an abandoned one at collection.

    A setup that run_once gave up on, or was cancelled away from, has no other reader; its failure
    was remembered and reported at that point.
    """
    if not setup.cancelled():
        setup.exception()


def _ending_of(setup: asyncio.Future[None]) -> BaseException | None:
    """The exception a finished setup ended with, unless it is still running or simply cancelled."""
    if not setup.done() or setup.cancelled():
        return None
    return setup.exception()


_setup = TaskManagerSetup()


async def setup_task_manager_once() -> None:
    await _setup.run_once()
