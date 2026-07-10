"""Unit tests for the telemetry per-metric graceful-degradation helper.

The helper runs a single metric coroutine and isolates its failure: a raising
coroutine degrades to ``None`` (interpreted downstream as "source failed"),
while a coroutine that completes returns its value untouched — including a
falsy ``0`` (interpreted as "source succeeded with nothing to count").
"""

from __future__ import annotations

from infrahub.telemetry.utils import safe_metric


async def _raises() -> int:
    raise RuntimeError("metric source unavailable")


async def _returns_zero() -> int:
    return 0


async def _returns_value() -> int:
    return 42


async def test_raising_coroutine_degrades_to_none() -> None:
    assert await safe_metric(_raises()) is None


async def test_zero_result_is_preserved() -> None:
    result = await safe_metric(_returns_zero())
    assert result == 0
    assert result is not None


async def test_non_zero_result_is_preserved() -> None:
    assert await safe_metric(_returns_value()) == 42
