import time
from asyncio import gather, sleep

from infrahub import lock


async def do_nothing(id: str, wait_sec: int, lock_name: str = "test1") -> int:
    """Function for testing a simple lock."""
    async with lock.registry.get(name=lock_name):
        start_time = time.time_ns()
        await sleep(delay=wait_sec)
        end_time = time.time_ns()

    return id, start_time, end_time


async def do_nothing_global_graph(id=str, wait_sec=int) -> int:
    """Function for testing the global_graph_lock.
    After acquiring the locks, wait for the indicated amount and return the start time and the end time of the lock."""
    async with lock.registry.global_graph_lock():
        start_time = time.time_ns()
        await sleep(delay=wait_sec)
        end_time = time.time_ns()

    return id, start_time, end_time


async def test_simple_infrahub_lock():
    lock.initialize_lock(local_only=True)

    results = await gather(
        do_nothing(id="one", wait_sec=0.5),
        do_nothing(id="two", wait_sec=1),
    )

    results.sort(key=lambda x: x[1])
    assert results[0][2] <= results[1][1]


async def test_multi_global_graph_lock():
    lock.initialize_lock(local_only=True)

    results = await gather(
        do_nothing_global_graph(id="one", wait_sec=0.5),
        do_nothing_global_graph(id="two", wait_sec=1),
        do_nothing(id="tree", wait_sec=1, lock_name="local.schema"),
    )

    assert results[0][2] <= results[1][1]
    assert results[0][2] <= results[2][1]


def test_generate_name():
    generate_name = lock.InfrahubLockRegistry._generate_name

    assert generate_name("simple") == "simple"
    assert generate_name("simple.name") == "simple.name"
    assert generate_name("simple.name.test") == "simple.name.test"
    assert generate_name("simple.name", local=True) == "local.simple.name"
    assert generate_name("simple.name", namespace="other") == "other.simple.name"
    assert generate_name("simple", namespace="other", local=True) == "local.other.simple"
    assert generate_name("simple", namespace="other", local=False) == "global.other.simple"
