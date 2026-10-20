"""Run code that needs a Prefect run context, such as a step that writes to the flow run's log."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prefect import flow

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


async def call_in_flow[T](call: Callable[[], Awaitable[T]]) -> T:
    """Await the call inside a flow run and return its result, re-raising what it raises."""
    results: list[T] = []

    @flow(name="call-in-flow")
    async def _run() -> None:
        results.append(await call())

    await _run()
    return results[0]
