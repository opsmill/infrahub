"""Seeding helpers shared by the integration recompute suites."""

from __future__ import annotations

import time
from asyncio import sleep
from typing import TYPE_CHECKING

from infrahub_sdk.task.models import TaskFilter, TaskState

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient


async def wait_idle(client: InfrahubClient, *, max_wait: int = 3600) -> None:
    """Wait for the task queue to drain.

    Raises:
        TimeoutError: if tasks are still pending at the deadline.

    """
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        pending = await client.task.count(
            filters=TaskFilter(state=[TaskState.PENDING, TaskState.RUNNING, TaskState.SCHEDULED])
        )
        if pending == 0:
            return
        await sleep(1)
    raise TimeoutError("background tasks did not drain within the timeout")


async def wait_for_seed(
    client: InfrahubClient, *, kind: str, attribute: str, expected: int, max_wait: int = 300
) -> None:
    """Wait for the transform to have run for every seeded node, nudging it once if it has not.

    The node-input automations are reconciled asynchronously after the repository import, so nodes
    created inside that window raise no event anyone is listening for. Draining the queue cannot
    detect it, because no task was ever created. Saving the nodes again once the automations exist
    produces the event they missed.

    Raises:
        AssertionError: if the value is still missing after the second attempt.

    """
    for attempt in range(2):
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            nodes = await client.all(kind=kind, branch="main")
            if sum(1 for node in nodes if getattr(node, attribute).value) == expected:
                return
            await sleep(2)
        if attempt == 0:
            for node in await client.all(kind=kind, branch="main"):
                node.name.value = f"{node.name.value}."
                await node.save()
            await wait_idle(client)
    raise AssertionError(f"{attribute} was not computed for all {expected} nodes of {kind}")
