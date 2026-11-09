from __future__ import annotations

import asyncio

from infrahub.api.admission.priority import Priority
from infrahub.api.admission.slot_pool import PrioritySlotPool
from tests.unit.api.admission.helpers import FailingSlotPoolObserver, FakeClock, RecordingSlotPoolObserver


async def _wait_until_waiting(pool: PrioritySlotPool, *, priority: Priority, count: int) -> None:
    """Yield to the loop until ``count`` tasks are parked in the priority's waiter queue.

    Raises:
        AssertionError: If the waiter count is never reached, so a wiring bug surfaces as a
            failure rather than a hang.

    """
    for _ in range(1000):
        if pool.waiters(priority=priority) >= count:
            return
        await asyncio.sleep(0)
    raise AssertionError(f"waiters for {priority} never reached {count}")


async def test_freed_slot_goes_to_highest_priority_waiter() -> None:
    pool = PrioritySlotPool(max_concurrency=1, observers=[])
    events: list[str] = []

    holder = await pool.acquire(priority=Priority.MEDIUM)
    assert pool.available == 0

    async def waiter(name: str, priority: Priority) -> None:
        acquisition = await pool.acquire(priority=priority)
        events.append(name)
        pool.release(acquisition=acquisition)

    low = asyncio.create_task(waiter("low", Priority.LOW))
    await _wait_until_waiting(pool, priority=Priority.LOW, count=1)
    high = asyncio.create_task(waiter("high", Priority.HIGH))
    await _wait_until_waiting(pool, priority=Priority.HIGH, count=1)

    # Both classes are queued behind the single held slot; releasing it once must wake the
    # HIGH waiter first even though LOW enqueued earlier.
    pool.release(acquisition=holder)

    await asyncio.gather(low, high)
    assert events == ["high", "low"]
    assert pool.available == 1
    assert pool.in_flight(priority=Priority.HIGH) == 0
    assert pool.in_flight(priority=Priority.LOW) == 0


async def test_within_class_fifo() -> None:
    pool = PrioritySlotPool(max_concurrency=1, observers=[])
    events: list[str] = []

    holder = await pool.acquire(priority=Priority.MEDIUM)

    async def waiter(name: str) -> None:
        acquisition = await pool.acquire(priority=Priority.MEDIUM)
        events.append(name)
        pool.release(acquisition=acquisition)

    tasks = []
    for name in ("first", "second", "third"):
        tasks.append(asyncio.create_task(waiter(name)))
        await _wait_until_waiting(pool, priority=Priority.MEDIUM, count=len(tasks))

    pool.release(acquisition=holder)
    await asyncio.gather(*tasks)

    assert events == ["first", "second", "third"]
    assert pool.available == 1


async def test_cancelled_waiter_leaks_no_slot() -> None:
    clock = FakeClock()
    pool = PrioritySlotPool(max_concurrency=1, observers=[], clock=clock)

    holder = await pool.acquire(priority=Priority.MEDIUM)

    cancelled_started = asyncio.Event()

    async def cancellable() -> None:
        cancelled_started.set()
        await pool.acquire(priority=Priority.LOW)

    victim = asyncio.create_task(cancellable())
    await cancelled_started.wait()
    await _wait_until_waiting(pool, priority=Priority.LOW, count=1)

    survivor_ran = asyncio.Event()

    async def survivor() -> None:
        acquisition = await pool.acquire(priority=Priority.MEDIUM)
        survivor_ran.set()
        pool.release(acquisition=acquisition)

    runner = asyncio.create_task(survivor())
    await _wait_until_waiting(pool, priority=Priority.MEDIUM, count=1)

    # Cancel the queued LOW waiter, then free the slot. The freed slot must reach the
    # MEDIUM survivor with no leak and no deadlock.
    victim.cancel()
    with_result = await asyncio.gather(victim, return_exceptions=True)
    assert isinstance(with_result[0], asyncio.CancelledError)
    assert pool.waiters(priority=Priority.LOW) == 0

    pool.release(acquisition=holder)
    await asyncio.wait_for(runner, timeout=1)
    assert survivor_ran.is_set()

    # Accounting invariant: every slot returned, nothing in flight.
    assert pool.available == pool.max_concurrency
    assert all(pool.in_flight(priority=priority) == 0 for priority in Priority)
    assert all(pool.waiters(priority=priority) == 0 for priority in Priority)


async def test_observer_reflects_waiters_while_still_queued() -> None:
    observer = RecordingSlotPoolObserver()
    pool = PrioritySlotPool(max_concurrency=1, observers=[observer])

    holder = await pool.acquire(priority=Priority.MEDIUM)

    async def waiter() -> None:
        acquisition = await pool.acquire(priority=Priority.LOW)
        pool.release(acquisition=acquisition)

    tasks = [asyncio.create_task(waiter()) for _ in range(3)]
    await _wait_until_waiting(pool, priority=Priority.LOW, count=3)

    # The observer must see the queue depth build up while the tasks are still parked,
    # before any slot is released — not only once a waiter is later dequeued.
    assert observer.waiters[Priority.LOW] == 3

    pool.release(acquisition=holder)
    await asyncio.gather(*tasks)
    # Draining brings the observed depth back to zero.
    assert observer.waiters[Priority.LOW] == 0


async def test_every_observer_receives_the_counts() -> None:
    first = RecordingSlotPoolObserver()
    second = RecordingSlotPoolObserver()
    pool = PrioritySlotPool(max_concurrency=2, observers=[first, second])

    holder = await pool.acquire(priority=Priority.HIGH)

    # Both sinks track the same transition: the pool fans out rather than keeping one slot.
    assert first.in_flight[Priority.HIGH] == 1
    assert second.in_flight[Priority.HIGH] == 1

    pool.release(acquisition=holder)
    assert first.in_flight[Priority.HIGH] == 0
    assert second.in_flight[Priority.HIGH] == 0


async def test_observer_reflects_cancelled_waiter_leaving_queue() -> None:
    observer = RecordingSlotPoolObserver()
    pool = PrioritySlotPool(max_concurrency=1, observers=[observer])

    holder = await pool.acquire(priority=Priority.MEDIUM)

    async def cancellable() -> None:
        await pool.acquire(priority=Priority.LOW)

    victim = asyncio.create_task(cancellable())
    await _wait_until_waiting(pool, priority=Priority.LOW, count=1)
    assert observer.waiters[Priority.LOW] == 1

    victim.cancel()
    results = await asyncio.gather(victim, return_exceptions=True)
    assert isinstance(results[0], asyncio.CancelledError)

    # Leaving the queue via cancellation must refresh the observer, not leave it stale at 1.
    assert observer.waiters[Priority.LOW] == 0
    pool.release(acquisition=holder)


async def test_failing_observer_does_not_corrupt_admission_state() -> None:
    survivor = RecordingSlotPoolObserver()
    # The failing sink is ordered first, so a shared guard would swallow the survivor too.
    pool = PrioritySlotPool(max_concurrency=1, observers=[FailingSlotPoolObserver(), survivor])

    # Acquire and release must both complete despite the first observer raising on every
    # transition, and the slot must be returned so a following waiter is served rather than
    # deadlocked.
    holder = await pool.acquire(priority=Priority.MEDIUM)
    assert pool.available == 0

    pool.release(acquisition=holder)

    assert pool.available == pool.max_concurrency
    assert all(pool.in_flight(priority=priority) == 0 for priority in Priority)

    # Isolation is per observer: the sink behind the failing one still saw both transitions.
    assert survivor.calls == 2
    assert survivor.in_flight[Priority.MEDIUM] == 0

    # A fresh acquire still succeeds on the recovered slot.
    again = await pool.acquire(priority=Priority.LOW)
    pool.release(acquisition=again)
    assert pool.available == pool.max_concurrency


async def test_cancel_after_handoff_rereleases_slot() -> None:
    pool = PrioritySlotPool(max_concurrency=1, observers=[])

    holder = await pool.acquire(priority=Priority.MEDIUM)

    async def cancellable() -> None:
        await pool.acquire(priority=Priority.HIGH)

    victim = asyncio.create_task(cancellable())
    await _wait_until_waiting(pool, priority=Priority.HIGH, count=1)

    survivor_ran = asyncio.Event()

    async def survivor() -> None:
        acquisition = await pool.acquire(priority=Priority.MEDIUM)
        survivor_ran.set()
        pool.release(acquisition=acquisition)

    runner = asyncio.create_task(survivor())
    await _wait_until_waiting(pool, priority=Priority.MEDIUM, count=1)

    # Freeing the slot hands it to the HIGH victim (highest priority). Cancelling the victim
    # in the same tick, before it consumes the slot, must re-release it to the MEDIUM
    # survivor rather than leak it.
    pool.release(acquisition=holder)
    victim.cancel()

    results = await asyncio.gather(victim, return_exceptions=True)
    assert isinstance(results[0], asyncio.CancelledError)

    await asyncio.wait_for(runner, timeout=1)
    assert survivor_ran.is_set()
    assert pool.available == pool.max_concurrency
    assert all(pool.in_flight(priority=priority) == 0 for priority in Priority)
