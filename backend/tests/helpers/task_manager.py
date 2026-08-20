"""Run the Prefect task manager setup once per test process.

The task manager setup registers blocks, worker pools, deployments and builtin
triggers against the per-process Prefect test server. The inputs are static and
the calls are slow (several seconds of API round-trips), so fixtures should reuse
a single setup per process instead of repeating it for every test or test class.

A failure is remembered the same way a success is. An unreachable Prefect test
server does not fail fast — the setup blocks until the pytest timeout fires — so
retrying it for every later test class costs that timeout each time and buries the
original cause under a wall of identical errors.

Tests that intentionally corrupt the shared task manager state must restore it
themselves before yielding back, otherwise later tests will observe the corruption.
"""

from collections.abc import Awaitable, Callable

from infrahub.workflows.initialization import setup_task_manager


class TaskManagerSetup:
    def __init__(self, setup: Callable[[], Awaitable[None]] = setup_task_manager) -> None:
        self._setup = setup
        self._initialized = False
        self._failure: BaseException | None = None

    async def run_once(self) -> None:
        if self._failure is not None:
            raise RuntimeError("Prefect task manager setup already failed in this process") from self._failure

        if self._initialized:
            return

        try:
            await self._setup()
        # The pytest timeout raises Failed, which derives from BaseException, and that is
        # the failure worth remembering most.
        except BaseException as exc:
            self._failure = exc
            raise

        self._initialized = True


_setup = TaskManagerSetup()


async def setup_task_manager_once() -> None:
    await _setup.run_once()
