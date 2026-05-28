from __future__ import annotations

import asyncio


class HealthyProbe:
    """Probe target that always reports healthy."""

    async def is_healthy(self) -> bool:
        return True


class UnhealthyProbe:
    """Probe target that reports unhealthy via a False return value."""

    async def is_healthy(self) -> bool:
        return False


class FailingProbe:
    """Probe target that raises a configured exception."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def is_healthy(self) -> bool:
        raise self._exc


class SlowProbe:
    """Probe target that sleeps long enough to exceed the health check timeout."""

    def __init__(self, delay: float = 10.0) -> None:
        self._delay = delay

    async def is_healthy(self) -> bool:
        await asyncio.sleep(self._delay)
        return True
