import asyncio
from collections.abc import Callable
from typing import Any

import pytest
from pytest_benchmark.fixture import BenchmarkFixture


@pytest.fixture
async def exec_async() -> Callable[..., Any]:
    def _wrapper(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if asyncio.iscoroutinefunction(func):

            def _() -> Any:
                return asyncio.get_event_loop().run_until_complete(func(*args, **kwargs))

            return _()

        return func(*args, **kwargs)

    return _wrapper


@pytest.fixture
async def aio_benchmark(benchmark: BenchmarkFixture) -> Callable[..., Any]:
    def _wrapper(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if asyncio.iscoroutinefunction(func):

            @benchmark
            def _() -> Any:
                return asyncio.get_event_loop().run_until_complete(func(*args, **kwargs))
        else:
            return benchmark(func, *args, **kwargs)

        return None

    return _wrapper
