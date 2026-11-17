import asyncio
import inspect
from collections.abc import Callable, Generator
from typing import Any

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from infrahub import config


@pytest.fixture(scope="module", autouse=True)
def _production_schema_operations_check() -> Generator[None, None, None]:
    """Measure schema loads with the operations check of production, which checks nothing."""
    previous_check = config.OVERRIDE.schema_operations_check
    config.OVERRIDE.schema_operations_check = None
    yield
    config.OVERRIDE.schema_operations_check = previous_check


@pytest.fixture
async def exec_async() -> Callable[..., Any]:
    def _wrapper(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if inspect.iscoroutinefunction(func):

            def _() -> Any:
                return asyncio.get_event_loop().run_until_complete(func(*args, **kwargs))

            return _()

        return func(*args, **kwargs)

    return _wrapper


@pytest.fixture
async def aio_benchmark(benchmark: BenchmarkFixture) -> Callable[..., Any]:
    def _wrapper(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if inspect.iscoroutinefunction(func):

            @benchmark
            def _() -> Any:
                return asyncio.get_event_loop().run_until_complete(func(*args, **kwargs))
        else:
            return benchmark(func, *args, **kwargs)

        return None

    return _wrapper
