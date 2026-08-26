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
server does not fail fast — the setup blocks until the pytest timeout fires — so
retrying it for every later test class costs that timeout each time and buries the
original cause under a wall of identical errors.

Tests that intentionally corrupt the shared task manager state must restore it
themselves before yielding back, otherwise later tests will observe the corruption.
"""

from collections.abc import Awaitable, Callable

from prefect.settings import get_current_settings

from infrahub.workflows.initialization import setup_task_manager


def _current_prefect_api_url() -> str | None:
    return get_current_settings().api.url


class TaskManagerSetup:
    def __init__(
        self,
        setup: Callable[[], Awaitable[None]] = setup_task_manager,
        server_key: Callable[[], str | None] = _current_prefect_api_url,
    ) -> None:
        self._setup = setup
        self._server_key = server_key
        self._initialized: set[str | None] = set()
        self._failures: dict[str | None, BaseException] = {}

    async def run_once(self) -> None:
        server = self._server_key()

        if server in self._failures:
            raise RuntimeError(f"Prefect task manager setup already failed for {server}") from self._failures[server]

        if server in self._initialized:
            return

        try:
            await self._setup()
        # The pytest timeout raises Failed, which derives from BaseException, and that is
        # the failure worth remembering most.
        except BaseException as exc:
            self._failures[server] = exc
            raise

        self._initialized.add(server)


_setup = TaskManagerSetup()


async def setup_task_manager_once() -> None:
    await _setup.run_once()
