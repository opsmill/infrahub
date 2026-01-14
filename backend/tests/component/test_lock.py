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


async def test_simple_infrahub_lock() -> None:
    lock.initialize_lock(local_only=True)

    results = await gather(
        do_nothing(id="one", wait_sec=0.5),
        do_nothing(id="two", wait_sec=1),
    )

    results.sort(key=lambda x: x[1])
    assert results[0][2] <= results[1][1]


async def test_multi_global_graph_lock() -> None:
    lock.initialize_lock(local_only=True)

    results = await gather(
        do_nothing_global_graph(id="one", wait_sec=0.5),
        do_nothing_global_graph(id="two", wait_sec=1),
        do_nothing(id="tree", wait_sec=1, lock_name="local.schema"),
    )

    assert results[0][2] <= results[1][1]
    assert results[0][2] <= results[2][1]


def test_generate_name() -> None:
    generate_name = lock.LockNameGenerator().generate_name

    assert generate_name("simple") == "simple"
    assert generate_name("simple.name") == "simple.name"
    assert generate_name("simple.name.test") == "simple.name.test"
    assert generate_name("simple.name", local=True) == "local.simple.name"
    assert generate_name("simple.name", namespace="other") == "other.simple.name"
    assert generate_name("simple", namespace="other", local=True) == "local.other.simple"
    assert generate_name("simple", namespace="other", local=False) == "global.other.simple"


def test_unpack_name() -> None:
    unpack_name = lock.LockNameGenerator().unpack_name

    assert unpack_name("simple") == ("simple", None, None)
    assert unpack_name("repository.simple") == ("simple", "repository", None)
    assert unpack_name("repository.simple-test") == ("simple-test", "repository", None)
    assert unpack_name("repository.simple-test.long-name") == ("simple-test.long-name", "repository", None)
    assert unpack_name("local.repository.simple") == ("simple", "repository", True)
    assert unpack_name("global.repository.simple") == ("simple", "repository", False)


async def test_reentrant_lock_allows_nested_acquisitions() -> None:
    lock.initialize_lock(local_only=True)

    events: list[str] = []

    async def reentrant_task() -> None:
        async with lock.registry.get(name="resource_pool.test"):
            events.append("outer acquired")
            async with lock.registry.get(name="resource_pool.test"):
                events.append("inner acquired")
                await sleep(delay=0.1)
            events.append("inner released")
            await sleep(delay=0.1)
        events.append("outer released")

    async def waiting_task() -> None:
        await sleep(delay=0.05)
        async with lock.registry.get(name="resource_pool.test"):
            events.append("waiter acquired")

    await gather(reentrant_task(), waiting_task())

    assert events == [
        "outer acquired",
        "inner acquired",
        "inner released",
        "outer released",
        "waiter acquired",
    ]
