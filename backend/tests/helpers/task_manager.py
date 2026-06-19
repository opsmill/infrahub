"""Run the Prefect task manager setup once per test process.

The task manager setup registers blocks, worker pools, deployments and builtin
triggers against the per-process Prefect test server. The inputs are static and
the calls are slow (several seconds of API round-trips), so fixtures should reuse
a single setup per process instead of repeating it for every test or test class.

Tests that intentionally corrupt the shared task manager state must restore it
themselves before yielding back, otherwise later tests will observe the corruption.
"""

from infrahub.workflows.initialization import setup_task_manager

_state = {"initialized": False}


async def setup_task_manager_once() -> None:
    if _state["initialized"]:
        return
    await setup_task_manager()
    _state["initialized"] = True
