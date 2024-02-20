import asyncio

import pytest


@pytest.fixture
async def aio_benchmark(benchmark, event_loop):
    def _wrapper(func, *args, **kwargs):
        if asyncio.iscoroutinefunction(func):

            @benchmark
            def _():
                return event_loop.run_until_complete(func(*args, **kwargs))
        else:
            return benchmark(func, *args, **kwargs)

    return _wrapper
